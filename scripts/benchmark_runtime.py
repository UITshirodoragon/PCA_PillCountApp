from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.constants import INFER_H, INFER_W
from app.services.infer_service import InferConfig, ModelRunner


DEFAULT_PYTORCH = {
    "PANetNano": "./Networks/weights/model_best_nano.pth",
    "PANetBase": "./Networks/weights/model_best_base.pth",
    "PANet": "./Networks/weights/model_best_base.pth",
}
DEFAULT_ONNX = {
    "PANetNano": "./Networks/weights/model_best_nano.onnx",
    "PANetBase": "./Networks/weights/model_best_base.onnx",
    "PANet": "./Networks/weights/model_best_base.onnx",
}


def _load_frame(path: str) -> np.ndarray:
    if path:
        frame = cv2.imread(path, cv2.IMREAD_COLOR)
        if frame is None:
            raise FileNotFoundError(path)
    else:
        frame = np.full((INFER_H, INFER_W, 3), 127, dtype=np.uint8)

    if frame.shape[:2] != (INFER_H, INFER_W):
        frame = cv2.resize(frame, (INFER_W, INFER_H), interpolation=cv2.INTER_LINEAR)
    return frame


def _make_cfg(args: argparse.Namespace) -> InferConfig:
    return InferConfig(
        thr_ratio=float(args.threshold),
        ksize=int(args.nms_ksize),
        min_peak=float(args.min_peak),
        max_peaks=int(args.max_peaks),
        smoothing_alpha=float(args.smoothing_alpha),
        torch_num_threads=int(args.cpu_threads),
        roi_enabled=bool(args.roi),
        roi_x=int(args.roi_x),
        roi_y=int(args.roi_y),
        roi_w=int(args.roi_w),
        roi_h=int(args.roi_h),
    )


def _runtime_path(args: argparse.Namespace, runtime: str) -> str:
    if runtime == "onnx":
        return args.onnx_model or DEFAULT_ONNX[args.arch]
    return args.pytorch_model or DEFAULT_PYTORCH[args.arch]


def run_runtime(args: argparse.Namespace, runtime: str, frame: np.ndarray) -> None:
    cfg = _make_cfg(args)
    runner = ModelRunner()
    runner.configure_runtime(int(args.cpu_threads))
    model_path = _runtime_path(args, runtime)
    runner.load(model_path, args.arch, runtime)

    last = None
    for _ in range(max(0, int(args.warmup))):
        last = runner.infer(frame, cfg)

    times_ms = []
    for _ in range(max(1, int(args.iters))):
        t0 = time.perf_counter()
        last = runner.infer(frame, cfg)
        times_ms.append((time.perf_counter() - t0) * 1000.0)

    count, centers, _mask_u8, score_map = last
    avg_ms = float(np.mean(times_ms))
    p95_ms = float(np.percentile(times_ms, 95))
    fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
    peak = float(np.max(score_map)) if score_map.size else 0.0
    print(
        f"{runtime:7s} arch={args.arch} count={count} centers={len(centers)} "
        f"avg_ms={avg_ms:.2f} p95_ms={p95_ms:.2f} fps={fps:.2f} "
        f"peak={peak:.4f} path={model_path}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PillCounter inference through PyTorch and/or ONNX.")
    parser.add_argument("--runtime", default="both", choices=["pytorch", "onnx", "both"], help="Backend to benchmark.")
    parser.add_argument("--arch", default="PANetNano", choices=["PANetNano", "PANetBase", "PANet"], help="Network architecture key.")
    parser.add_argument("--pytorch-model", default="", help="Path to .pth checkpoint. Defaults by --arch.")
    parser.add_argument("--onnx-model", default="", help="Path to .onnx model. Defaults by --arch.")
    parser.add_argument("--image", default="", help="Optional BGR/RGB image path. If omitted, uses a gray test frame.")
    parser.add_argument("--iters", type=int, default=20, help="Timed inference iterations.")
    parser.add_argument("--warmup", type=int, default=3, help="Warmup iterations before timing.")
    parser.add_argument("--cpu-threads", type=int, default=1, help="CPU threads for PyTorch or ONNX Runtime.")
    parser.add_argument("--threshold", type=float, default=0.45, help="Postprocess relative threshold, e.g. 0.45.")
    parser.add_argument("--nms-ksize", type=int, default=5, help="Postprocess NMS kernel size.")
    parser.add_argument("--min-peak", type=float, default=0.25, help="Postprocess absolute minimum peak.")
    parser.add_argument("--max-peaks", type=int, default=500, help="Postprocess peak cap.")
    parser.add_argument("--smoothing-alpha", type=float, default=0.0, help="EMA smoothing alpha.")
    parser.add_argument("--roi", action="store_true", help="Enable ROI mask before counting.")
    parser.add_argument("--roi-x", type=int, default=32)
    parser.add_argument("--roi-y", type=int, default=16)
    parser.add_argument("--roi-w", type=int, default=280)
    parser.add_argument("--roi-h", type=int, default=208)
    return parser.parse_args()


def main() -> None:
    os.chdir(ROOT)
    args = parse_args()
    frame = _load_frame(args.image)
    runtimes = ("pytorch", "onnx") if args.runtime == "both" else (args.runtime,)
    for runtime in runtimes:
        run_runtime(args, runtime, frame)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
