from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from app.core.bus import MessageBus
from app.core.types import AppEvent, AppEventType, InferResult
from app.services.infer_service import ModelRunner, InferConfig

log = logging.getLogger("infer_worker")


class InferWorker(QObject):
    infer_ready = pyqtSignal(object)   # InferResult
    status_changed = pyqtSignal(bool)  # model loaded

    def __init__(self, bus: MessageBus):
        super().__init__()
        self.bus = bus
        self.runner = ModelRunner()
        self.cfg = InferConfig()
        self._running = False
        self._freeze = False
        self._target_fps = 8
        self._last_infer_ms = 0

        self._model_path = ""
        self._model_arch = ""

    @pyqtSlot(str, str)
    def set_model(self, model_path: str, model_arch: str):
        self._model_path = model_path or ""
        self._model_arch = model_arch or ""
        # lazy load in loop

    @pyqtSlot(int, float, int, int, int)
    def set_params(self, target_fps: int, smoothing_alpha: float, ksize: int, max_peaks: int, thr_ratio_pct: int):
        self._target_fps = max(1, int(target_fps))
        self.cfg.smoothing_alpha = float(smoothing_alpha)
        self.cfg.ksize = int(ksize)
        self.cfg.max_peaks = int(max_peaks)
        self.cfg.thr_ratio = max(0.01, min(0.99, float(thr_ratio_pct) / 100.0))

    @pyqtSlot(bool)
    def set_freeze(self, freeze: bool):
        self._freeze = bool(freeze)

    @pyqtSlot()
    def start(self):
        self._running = True
        self._loop()

    @pyqtSlot()
    def stop(self):
        self._running = False

    def _try_load(self):
        if not self._model_path or not self._model_arch:
            return False
        try:
            self.runner.load(self._model_path, self._model_arch)
            self.status_changed.emit(True)
            self.bus.publish(AppEvent(AppEventType.LOG, "infer", "model_loaded"))
            return True
        except Exception as e:
            self.status_changed.emit(False)
            self.bus.publish(AppEvent(AppEventType.ERROR, "infer", f"Model load failed: {e}"))
            return False

    def _loop(self):
        model_ok = False
        while self._running:
            if not model_ok:
                model_ok = self._try_load()

            if self._freeze:
                time.sleep(0.02)
                continue

            # throttle
            now_ms = int(time.time() * 1000)
            interval = int(1000 / max(1, self._target_fps))
            if now_ms - self._last_infer_ms < interval:
                time.sleep(0.001)
                continue

            fr = self.bus.get_latest_frame()
            if fr is None:
                time.sleep(0.005)
                continue

            try:
                count, centers, mask_u8, score_map = self.runner.infer(fr.bgr, self.cfg)
                res = InferResult(ts_ms=fr.ts_ms, count=count, centers=centers, mask_u8=mask_u8, score_map=score_map)
                self._last_infer_ms = now_ms
                self.infer_ready.emit(res)
                self.bus.infer_updated.emit(res)
            except Exception as e:
                self.bus.publish(AppEvent(AppEventType.ERROR, "infer", f"Infer failed: {e}"))
                time.sleep(0.02)
