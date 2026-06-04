from __future__ import annotations

import threading
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from app.core.types import AppEvent, Frame, InferResult, WeightStatus


class MessageBus(QObject):
    """Internal gateway that provides:
    - latest-frame buffer (drop old frames)
    - event publishing
    - clear/flush primitives (lightweight)
    """

    event_published = pyqtSignal(object)      # AppEvent
    latest_frame_updated = pyqtSignal(object) # Frame (optional for debug)
    infer_updated = pyqtSignal(object)        # InferResult
    weight_updated = pyqtSignal(object)       # WeightStatus

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._latest_frame: Optional[Frame] = None

    def publish(self, ev: AppEvent) -> None:
        self.event_published.emit(ev)

    def set_latest_frame(self, frame: Frame) -> None:
        with self._lock:
            self._latest_frame = frame
        self.latest_frame_updated.emit(frame)

    def get_latest_frame(self) -> Optional[Frame]:
        with self._lock:
            return self._latest_frame

    def clear_latest_frame(self) -> None:
        with self._lock:
            self._latest_frame = None
