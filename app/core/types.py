from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
import numpy as np


class OpType(str, Enum):
    RECEIVE = "add"
    DISPENSE = "remove"
    COUNT_ONLY = "count_only"


class AppEventType(str, Enum):
    LOG = "log"
    CAMERA_STATUS = "camera_status"
    SERIAL_STATUS = "serial_status"
    WEIGHT = "weight"
    FLASK_STATUS = "flask_status"
    ERROR = "error"


@dataclass
class Frame:
    bgr: np.ndarray  # HxWx3 uint8
    ts_ms: int


@dataclass
class InferResult:
    ts_ms: int
    count: int
    centers: List[Tuple[int, int]]  # (x,y) in inference coords
    mask_u8: np.ndarray  # HxW uint8 0..255 (binary or heat)
    score_map: Optional[np.ndarray] = None  # HxW float (optional)


@dataclass
class WeightStatus:
    ts_ms: int
    weight_g: float
    stable: bool


@dataclass
class AppEvent:
    typ: AppEventType
    source: str
    message: str
    payload: Optional[object] = None
