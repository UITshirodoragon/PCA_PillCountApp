from __future__ import annotations

"""Pre/post-processing for pill counting density/heatmap models.

Assumptions:
- Input: BGR uint8 image (H,W,3) at 320x240.
- Model output: a single-channel map (density/heat) in shape:
  (1,1,H,W) or (1,H,W) or (H,W).

This module provides:
- ImageNet normalization preprocess (commonly used in your training code)
- LMDS-style local maxima extraction using max-pooling
- Simple overlay rendering utilities (mask + centers + count)
"""

from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F


_IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
_IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


@dataclass
class LmdsConfig:
    thr_ratio: float = 0.25     # threshold relative to max
    ksize: int = 5              # max-pool kernel for local maxima
    min_peak: float = 0.0       # absolute score threshold
    min_max: float = 1e-6       # ignore maps with too small max
    max_peaks: int = 500        # cap peaks for safety


def imagenet_preprocess_bgr(frame_bgr: np.ndarray) -> torch.Tensor:
    """BGR uint8 -> RGB float tensor (1,3,H,W) normalized by ImageNet mean/std."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    x = torch.from_numpy(rgb).float() / 255.0  # HWC
    x = x.permute(2, 0, 1).unsqueeze(0).contiguous()  # 1CHW
    return (x - _IMAGENET_MEAN) / _IMAGENET_STD


def _to_hw_map(pred: torch.Tensor) -> np.ndarray:
    if isinstance(pred, (tuple, list)):
        pred = pred[0]
    if pred.ndim == 4:
        pred = pred[0, 0]
    elif pred.ndim == 3:
        pred = pred[0]
    elif pred.ndim == 2:
        pass
    else:
        raise ValueError(f"Unexpected pred shape: {tuple(pred.shape)}")
    return pred.detach().cpu().float().numpy()


def lmds_from_map(map_hw: np.ndarray, cfg: LmdsConfig) -> Tuple[int, List[Tuple[int, int]], np.ndarray]:
    """Return (count, centers, mask_u8) where mask_u8 is binary 0/255."""
    m = map_hw.astype(np.float32)
    m[m < 0] = 0
    mmax = float(m.max()) if m.size else 0.0
    if mmax < cfg.min_max:
        return 0, [], np.zeros_like(m, dtype=np.uint8)

    t = torch.from_numpy(m).unsqueeze(0).unsqueeze(0)  # 1,1,H,W
    # local maxima
    k = int(cfg.ksize)
    if k < 3:
        k = 3
    if k % 2 == 0:
        k += 1
    pooled = F.max_pool2d(t, kernel_size=k, stride=1, padding=k // 2)
    abs_thr = max(float(cfg.thr_ratio) * mmax, float(cfg.min_peak))
    keep = (pooled == t) & (t >= abs_thr)
    ys, xs = torch.nonzero(keep[0, 0], as_tuple=True)
    centers = [(int(x.item()), int(y.item())) for x, y in zip(xs, ys)]
    if len(centers) > cfg.max_peaks:
        centers = centers[: cfg.max_peaks]
    mask = keep[0, 0].cpu().numpy().astype(np.uint8) * 255
    return int(len(centers)), centers, mask


def colorize_map(map_hw: np.ndarray) -> np.ndarray:
    """Map -> BGR heatmap for visualization."""
    m = map_hw.astype(np.float32)
    m[m < 0] = 0
    vmax = float(m.max()) if m.size else 0.0
    if vmax <= 0:
        m8 = np.zeros_like(m, dtype=np.uint8)
    else:
        m8 = np.clip(m / vmax * 255.0, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(m8, cv2.COLORMAP_JET)


def draw_overlay(frame_bgr: np.ndarray, centers: List[Tuple[int, int]], count: int, mask_u8: np.ndarray | None = None) -> np.ndarray:
    out = frame_bgr.copy()
    if mask_u8 is not None:
        # alpha blend mask in red channel (cheap)
        if mask_u8.shape[:2] != out.shape[:2]:
            mask_u8 = cv2.resize(mask_u8, (out.shape[1], out.shape[0]), interpolation=cv2.INTER_NEAREST)
        red = out[:, :, 2].astype(np.int16)
        red = np.clip(red + (mask_u8.astype(np.int16) // 3), 0, 255).astype(np.uint8)
        out[:, :, 2] = red

    for x, y in centers:
        cv2.circle(out, (int(x), int(y)), 3, (0, 0, 0), -1)
        cv2.circle(out, (int(x), int(y)), 2, (0, 255, 0), -1)

    cv2.putText(out, f"Count: {int(count)}", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)
    return out
