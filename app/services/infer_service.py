from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple, List

import numpy as np
import torch

from app.core.constants import INFER_H, INFER_W
from app.services.postprocess_utils import imagenet_preprocess_bgr

log = logging.getLogger("infer")


@dataclass
class InferConfig:
    thr_ratio: float = 0.25
    ksize: int = 5
    min_peak: float = 0.25
    min_max: float = 1e-6
    max_peaks: int = 500
    smoothing_alpha: float = 0.0  # EMA on output map to reduce jitter
    torch_num_threads: int = 1
    roi_enabled: bool = False
    roi_x: int = 0
    roi_y: int = 0
    roi_w: int = INFER_W
    roi_h: int = INFER_H


class ModelRunner:
    """Loads a PyTorch or ONNX model and runs CPU inference."""

    def __init__(self):
        self._model: Optional[torch.nn.Module] = None
        self._ort_session: Optional[object] = None
        self._ort_input_name: str = ""
        self._ort_output_name: str = ""
        self._runtime: str = "pytorch"
        self._device = torch.device("cpu")
        self._loaded_key: Tuple[str, str, str] | None = None  # (runtime, path, arch)
        self._ema: Optional[np.ndarray] = None
        self._torch_num_threads: Optional[int] = None

    def configure_runtime(self, num_threads: int) -> None:
        n = max(1, int(num_threads or 1))
        if self._torch_num_threads == n:
            return
        try:
            torch.set_num_threads(n)
            self._torch_num_threads = n
            log.info("Torch num_threads=%s", n)
        except Exception as e:
            log.warning("Cannot set torch num_threads=%s: %s", n, e)

    @staticmethod
    def _lmds_counting(m_use: np.ndarray, cfg: InferConfig) -> Tuple[int, List[Tuple[int, int]], np.ndarray]:
        """Peak counting compatible with MCU-friendly LMDS-like postprocess.

        Local maxima are extracted with configurable NMS and retained only when
        they pass both relative and absolute peak thresholds.
        Returns: count, centers, kpoint (binary map 0/1)
        """
        if m_use.ndim != 2:
            raise ValueError(f"Expected 2D map, got {m_use.shape}")

        m = m_use.astype(np.float32).copy()
        m[m < 0] = 0.0
        input_max = float(np.max(m)) if m.size else 0.0
        min_max = float(getattr(cfg, "min_max", 1e-6) or 0.0)
        if input_max <= min_max:
            return 0, [], np.zeros_like(m, dtype=np.uint8)

        t = torch.from_numpy(m).unsqueeze(0).unsqueeze(0)  # (1,1,H,W)
        input_max = float(torch.max(t).item())

        k = int(getattr(cfg, "ksize", 3) or 3)
        if k < 3:
            k = 3
        if k % 2 == 0:
            k += 1

        keep = torch.nn.functional.max_pool2d(t, (k, k), stride=1, padding=k // 2)
        keep = (keep == t).float()
        t = keep * t

        thr_ratio = float(getattr(cfg, "thr_ratio", 100.0 / 255.0))
        min_peak = float(getattr(cfg, "min_peak", 0.0) or 0.0)
        abs_thr = max(thr_ratio * input_max, min_peak)
        t[t < abs_thr] = 0.0
        t[t > 0.0] = 1.0

        # Convert to numpy kpoint
        kpoint = t.squeeze(0).squeeze(0).cpu().numpy().astype(np.uint8)

        # Optional cap peaks
        if int(getattr(cfg, "max_peaks", 0) or 0) > 0:
            max_peaks = int(cfg.max_peaks)
            coords = np.argwhere(kpoint > 0)
            if coords.shape[0] > max_peaks:
                scores = m_use[coords[:, 0], coords[:, 1]]
                order = np.argsort(-scores)
                keep_coords = coords[order[:max_peaks]]
                kpoint[...] = 0
                kpoint[keep_coords[:, 0], keep_coords[:, 1]] = 1

        coords = np.argwhere(kpoint > 0)
        centers = [(int(c[1]), int(c[0])) for c in coords]  # (x,y)
        count = int(len(centers))
        return count, centers, kpoint

    @staticmethod
    def _apply_roi(map_hw: np.ndarray, cfg: InferConfig) -> np.ndarray:
        if not bool(getattr(cfg, "roi_enabled", False)):
            return map_hw

        h, w = map_hw.shape[:2]
        sx = float(w) / float(INFER_W)
        sy = float(h) / float(INFER_H)
        x0 = int(round(max(0, int(getattr(cfg, "roi_x", 0) or 0)) * sx))
        y0 = int(round(max(0, int(getattr(cfg, "roi_y", 0) or 0)) * sy))
        rw = int(round(max(1, int(getattr(cfg, "roi_w", INFER_W) or INFER_W)) * sx))
        rh = int(round(max(1, int(getattr(cfg, "roi_h", INFER_H) or INFER_H)) * sy))
        x1 = min(w, x0 + rw)
        y1 = min(h, y0 + rh)
        if x0 >= x1 or y0 >= y1:
            return np.zeros_like(map_hw, dtype=np.float32)

        out = np.zeros_like(map_hw, dtype=np.float32)
        out[y0:y1, x0:x1] = map_hw[y0:y1, x0:x1]
        return out

    def is_loaded(self) -> bool:
        return self._model is not None or self._ort_session is not None

    def load(self, model_path: str, model_arch: str, runtime: str = "pytorch") -> None:
        runtime = (runtime or "pytorch").strip().lower()
        if runtime not in ("pytorch", "onnx"):
            raise ValueError(f"Unsupported model runtime '{runtime}'. Use 'pytorch' or 'onnx'.")
        model_path = os.path.abspath(model_path)
        if not os.path.exists(model_path):
            raise FileNotFoundError(model_path)
        if not model_arch:
            raise ValueError("Model arch is empty. Set Settings → Model arch (Networks.model_dict key).")

        if self._loaded_key == (runtime, model_path, model_arch) and self.is_loaded():
            return

        if runtime == "onnx":
            self._load_onnx(model_path, model_arch)
            return

        self._load_pytorch(model_path, model_arch)

    def _load_onnx(self, model_path: str, model_arch: str) -> None:
        try:
            import onnxruntime as ort
        except Exception as e:
            raise ImportError("ONNX runtime is not installed. Install requirements.txt or `pip install onnxruntime`.") from e

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = max(1, int(self._torch_num_threads or 1))
        sess_options.inter_op_num_threads = 1
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session = ort.InferenceSession(model_path, sess_options=sess_options, providers=["CPUExecutionProvider"])
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if not inputs:
            raise ValueError("ONNX model has no inputs")
        if not outputs:
            raise ValueError("ONNX model has no outputs")

        self._model = None
        self._ort_session = session
        self._ort_input_name = inputs[0].name
        self._ort_output_name = outputs[0].name
        self._runtime = "onnx"
        self._loaded_key = ("onnx", model_path, model_arch)
        self._ema = None
        log.info("Loaded ONNX model: %s (%s)", model_path, model_arch)

    def _load_pytorch(self, model_path: str, model_arch: str) -> None:

        try:
            from Networks import model_dict  # type: ignore
        except Exception as e:
            raise ImportError("Cannot import Networks.model_dict. Put your Networks package next to app.py or in PYTHONPATH.") from e

        if model_arch not in model_dict:
            raise KeyError(f"Model arch '{model_arch}' not in Networks.model_dict keys: {list(model_dict.keys())[:20]}")

        model = model_dict[model_arch]()
        ckpt = torch.load(model_path, map_location="cpu")

        if isinstance(ckpt, torch.nn.Module):
            model = ckpt
        elif isinstance(ckpt, dict):
            state = None
            for k in ("state_dict", "model_state_dict", "net", "model"):
                if k in ckpt and isinstance(ckpt[k], dict):
                    state = ckpt[k]
                    break
            if state is None and all(isinstance(v, torch.Tensor) for v in ckpt.values()):
                state = ckpt

            if state is None:
                raise ValueError("Unsupported checkpoint dict: cannot find state_dict.")

            new_state = {}
            for k, v in state.items():
                nk = k[7:] if isinstance(k, str) and k.startswith("module.") else k
                new_state[nk] = v
            missing, unexpected = model.load_state_dict(new_state, strict=False)
            if missing:
                log.warning("Missing keys: %s", missing[:20])
            if unexpected:
                log.warning("Unexpected keys: %s", unexpected[:20])
        else:
            raise ValueError("Unsupported checkpoint type for .pth")

        model.to(self._device)
        model.eval()

        self._model = model
        self._ort_session = None
        self._ort_input_name = ""
        self._ort_output_name = ""
        self._runtime = "pytorch"
        self._loaded_key = ("pytorch", model_path, model_arch)
        self._ema = None
        log.info("Loaded model: %s (%s)", model_path, model_arch)

    @torch.inference_mode()
    def infer(self, frame_bgr: np.ndarray, cfg: InferConfig) -> Tuple[int, List[Tuple[int, int]], np.ndarray, np.ndarray]:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded")

        # Ensure fixed size
        if frame_bgr.shape[0] != INFER_H or frame_bgr.shape[1] != INFER_W:
            import cv2
            frame_bgr = cv2.resize(frame_bgr, (INFER_W, INFER_H), interpolation=cv2.INTER_LINEAR)

        x = imagenet_preprocess_bgr(frame_bgr)

        if self._runtime == "onnx":
            if self._ort_session is None:
                raise RuntimeError("ONNX session not loaded")
            y_np = self._ort_session.run([self._ort_output_name], {self._ort_input_name: x.cpu().numpy().astype(np.float32)})[0]
            y = torch.from_numpy(y_np)
        else:
            if self._model is None:
                raise RuntimeError("PyTorch model not loaded")
            x = x.to(self._device)  # (1,3,H,W)
            y = self._model(x)
            if isinstance(y, (tuple, list)):
                y = y[0]
            if not isinstance(y, torch.Tensor):
                raise ValueError("Model output is not a Tensor")

        # map (H,W)
        if y.ndim == 4:
            m = y[0, 0].float().cpu().numpy()
        elif y.ndim == 3:
            m = y[0].float().cpu().numpy()
        elif y.ndim == 2:
            m = y.float().cpu().numpy()
        else:
            raise ValueError(f"Unexpected output shape: {tuple(y.shape)}")

        # EMA smoothing
        a = float(cfg.smoothing_alpha or 0.0)
        if a > 0:
            if self._ema is None or self._ema.shape != m.shape:
                self._ema = m.copy()
            else:
                self._ema = (1.0 - a) * self._ema + a * m
            m_use = self._ema
        else:
            m_use = m

        m_count = self._apply_roi(m_use, cfg)
        count, centers, kpoint = self._lmds_counting(m_count, cfg)

        # heat-mask for UI: normalized density map (stable visual) rather than sparse peaks
        mmax = float(np.max(m_count)) if m_count is not None else 0.0
        if mmax > 1e-8:
            mask_u8 = np.clip(m_count / mmax * 255.0, 0, 255).astype(np.uint8)
        else:
            mask_u8 = np.zeros_like(m_count, dtype=np.uint8)
        return count, centers, mask_u8, m_count.astype(np.float32)
