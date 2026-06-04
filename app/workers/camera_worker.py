from __future__ import annotations

import logging
import time
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from app.core.types import AppEvent, AppEventType, Frame
from app.services.camera_service import CameraService, CameraConfig
from app.core.bus import MessageBus

log = logging.getLogger("camera_worker")


class CameraWorker(QObject):
    frame_ready = pyqtSignal(object)   # Frame
    status_changed = pyqtSignal(bool)  # connected

    def __init__(self, bus: MessageBus, cfg: CameraConfig):
        super().__init__()
        self.bus = bus
        self.svc = CameraService(cfg)
        self._running = False
        self._emit_every_n = 1
        self._counter = 0

    @pyqtSlot()
    def start(self):
        self._running = True
        self._loop()

    @pyqtSlot()
    def stop(self):
        self._running = False
        self.svc.close()

    def _loop(self):
        last_status: Optional[bool] = None
        while self._running:
            if not self.svc.connected:
                self.svc.open()

            ok, frame = self.svc.read()
            if ok and frame is not None:
                ts_ms = int(time.time() * 1000)
                fr = Frame(bgr=frame, ts_ms=ts_ms)
                # put to bus for infer (drop old)
                self.bus.set_latest_frame(fr)

                # emit to UI (can be throttled if needed)
                self._counter += 1
                if (self._counter % self._emit_every_n) == 0:
                    self.frame_ready.emit(fr)

            st = bool(self.svc.connected)
            if last_status is None or st != last_status:
                last_status = st
                self.status_changed.emit(st)
                self.bus.publish(AppEvent(AppEventType.CAMERA_STATUS, "camera", "connected" if st else "disconnected"))
            time.sleep(0.005)
