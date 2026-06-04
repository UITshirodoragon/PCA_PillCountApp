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
    min_max: float = 1e-6
    max_peaks: int = 500
    smoothing_alpha: float = 0.0  # EMA on output map to reduce jitter


class ModelRunner:
    """Loads a .pth model using Networks.model_dict and runs CPU inference."""

    def __init__(self):
        self._model: Optional[torch.nn.Module] = None
        self._device = torch.device("cpu")
        self._loaded_key: Tuple[str, str] | None = None  # (path, arch)
        self._ema: Optional[np.ndarray] = None

    @staticmethod
    def _lmds_counting(m_use: np.ndarray, cfg: InferConfig) -> Tuple[int, List[Tuple[int, int]], np.ndarray]:
        """Peak counting compatible with MCU-friendly LMDS-like postprocess.

        Implemented to match the requested logic (3x3 local maxima + relative threshold).
        Returns: count, centers, kpoint (binary map 0/1)
        """
        if m_use.ndim != 2:
            raise ValueError(f"Expected 2D map, got {m_use.shape}")

        t = torch.from_numpy(m_use.astype(np.float32)).unsqueeze(0).unsqueeze(0)  # (1,1,H,W)
        input_max = float(torch.max(t).item())

        keep = torch.nn.functional.max_pool2d(t, (3, 3), stride=1, padding=1)
        keep = (keep == t).float()
        t = keep * t

        thr_ratio = float(getattr(cfg, "thr_ratio", 100.0 / 255.0))
        t[t < (thr_ratio * input_max)] = 0.0
        t[t > 0.0] = 1.0
        if input_max < 0.1:
            t = t * 0.0

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

    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self, model_path: str, model_arch: str) -> None:
        model_path = os.path.abspath(model_path)
        if not os.path.exists(model_path):
            raise FileNotFoundError(model_path)
        if not model_arch:
            raise ValueError("Model arch is empty. Set Settings → Model arch (Networks.model_dict key).")

        if self._loaded_key == (model_path, model_arch) and self._model is not None:
            return

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
        self._loaded_key = (model_path, model_arch)
        self._ema = None
        log.info("Loaded model: %s (%s)", model_path, model_arch)

    @torch.inference_mode()
    def infer(self, frame_bgr: np.ndarray, cfg: InferConfig) -> Tuple[int, List[Tuple[int, int]], np.ndarray, np.ndarray]:
        if self._model is None:
            raise RuntimeError("Model not loaded")

        # Ensure fixed size
        if frame_bgr.shape[0] != INFER_H or frame_bgr.shape[1] != INFER_W:
            import cv2
            frame_bgr = cv2.resize(frame_bgr, (INFER_W, INFER_H), interpolation=cv2.INTER_LINEAR)

        x = imagenet_preprocess_bgr(frame_bgr).to(self._device)  # (1,3,H,W)

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

        count, centers, kpoint = self._lmds_counting(m_use, cfg)

        # heat-mask for UI: normalized density map (stable visual) rather than sparse peaks
        mmax = float(np.max(m_use)) if m_use is not None else 0.0
        if mmax > 1e-8:
            mask_u8 = np.clip(m_use / mmax * 255.0, 0, 255).astype(np.uint8)
        else:
            mask_u8 = np.zeros_like(m_use, dtype=np.uint8)
        return count, centers, mask_u8, m_use.astype(np.float32)
