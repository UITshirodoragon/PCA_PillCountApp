from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from app.core.constants import INFER_H, INFER_W

log = logging.getLogger("camera")


@dataclass
class CameraConfig:
    device_index: int = 0
    width: int = INFER_W
    height: int = INFER_H
    fps: int = 30
    lock_controls: bool = True
    auto_exposure_value: float = 1.0
    exposure: float = 156.0
    gain: float = 0.0
    lock_white_balance: bool = True
    white_balance_temperature: int = 4500


class CameraService:
    def __init__(self, cfg: CameraConfig):
        self.cfg = cfg
        self.cap: Optional[cv2.VideoCapture] = None
        self.connected: bool = False
        self._last_open_try = 0.0

    def open(self) -> bool:
        now = time.time()
        if now - self._last_open_try < 1.0:
            return False
        self._last_open_try = now

        self.close()
        # Prefer V4L2 on Linux/Raspberry Pi; fallback is automatic if unavailable.
        cap = cv2.VideoCapture(self.cfg.device_index, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.cfg.device_index)
        if not cap.isOpened():
            log.warning("Cannot open camera index %s", self.cfg.device_index)
            self.connected = False
            self.cap = None
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.cfg.width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.cfg.height))
        cap.set(cv2.CAP_PROP_FPS, int(self.cfg.fps))
        self._apply_camera_controls(cap)

        self.cap = cap
        self.connected = True
        log.info("Camera opened: index=%s target=%sx%s@%s", self.cfg.device_index, self.cfg.width, self.cfg.height, self.cfg.fps)
        return True

    def _set_cap_prop(self, cap: cv2.VideoCapture, prop_name: str, value: float) -> None:
        prop = getattr(cv2, prop_name, None)
        if prop is None:
            return
        try:
            ok = bool(cap.set(prop, float(value)))
            got = cap.get(prop)
            log.info("Camera control %s set=%s read=%s ok=%s", prop_name, value, got, ok)
        except Exception as e:
            log.warning("Camera control %s failed: %s", prop_name, e)

    def _apply_camera_controls(self, cap: cv2.VideoCapture) -> None:
        if bool(getattr(self.cfg, "lock_controls", False)):
            self._set_cap_prop(cap, "CAP_PROP_AUTO_EXPOSURE", float(self.cfg.auto_exposure_value))
            self._set_cap_prop(cap, "CAP_PROP_EXPOSURE", float(self.cfg.exposure))
            self._set_cap_prop(cap, "CAP_PROP_GAIN", float(self.cfg.gain))

        if bool(getattr(self.cfg, "lock_white_balance", False)):
            self._set_cap_prop(cap, "CAP_PROP_AUTO_WB", 0.0)
            self._set_cap_prop(cap, "CAP_PROP_WB_TEMPERATURE", float(self.cfg.white_balance_temperature))

    def close(self) -> None:
        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass
        self.cap = None
        self.connected = False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.cap is None or not self.connected:
            return False, None

        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.connected = False
            return False, None

        frame = cv2.rotate(frame, cv2.ROTATE_180)

        # Keep preview and inference aligned at the configured model resolution.
        h, w = frame.shape[:2]
        if h != INFER_H or w != INFER_W:
            frame = cv2.resize(frame, (INFER_W, INFER_H), interpolation=cv2.INTER_LINEAR)
        return True, frame
