from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class CameraSettings:
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    profile: str = "balanced"  # fast | balanced | quality | custom


@dataclass
class ModelSettings:
    model_path: str = "./Networks/weights/model_best.pth"
    model_arch: str = "PANet"
    threshold: float = 0.4
    nms_ksize: int = 5
    min_peak: float = 0.25
    max_peaks: int = 500
    realtime_fps: int = 8
    smoothing_alpha: float = 0.0


@dataclass
class SerialSettings:
    # Kept only for backwards-compatible config loading. v0.1.3 runtime does not use Nucleo/HX711.
    port: str = "/dev/ttyACM0"
    baud: int = 115200
    stream_weight: bool = False
    stable_window: int = 8
    enabled: bool = False


@dataclass
class ShareSettings:
    enable_qr_share: bool = True
    port: int = 5000
    bind_all: bool = True
    token_required: bool = True


@dataclass
class CloudflareSettings:
    enabled: bool = True
    cloudflared_path: str = "cloudflared"
    auto_start: bool = True
    public_url: str = ""


@dataclass
class StorageSettings:
    root_dir: str = "storage"
    reports_dir: str = "storage/reports"
    logs_dir: str = "storage/logs"


@dataclass
class AppConfig:
    camera: CameraSettings = field(default_factory=CameraSettings)
    model: ModelSettings = field(default_factory=ModelSettings)
    serial: SerialSettings = field(default_factory=SerialSettings)
    share: ShareSettings = field(default_factory=ShareSettings)
    cloudflare: CloudflareSettings = field(default_factory=CloudflareSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)

    @staticmethod
    def default() -> "AppConfig":
        return AppConfig()

    @staticmethod
    def load(path: str) -> "AppConfig":
        if not os.path.exists(path):
            cfg = AppConfig.default()
            cfg.save(path)
            return cfg

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}

        def _load_dc(dc_cls, d):
            d = d or {}
            kwargs = {}
            for k in dc_cls.__dataclass_fields__.keys():
                if k in d:
                    kwargs[k] = d[k]
            return dc_cls(**kwargs)

        cfg = AppConfig(
            camera=_load_dc(CameraSettings, data.get("camera", {})),
            model=_load_dc(ModelSettings, data.get("model", {})),
            serial=_load_dc(SerialSettings, data.get("serial", {})),
            share=_load_dc(ShareSettings, data.get("share", {})),
            cloudflare=_load_dc(CloudflareSettings, data.get("cloudflare", {})),
            storage=_load_dc(StorageSettings, data.get("storage", {})),
        )

        # v0.1.3: hard-disable serial at runtime even if old config has stream_weight=true.
        cfg.serial.enabled = False
        cfg.serial.stream_weight = False

        Path(cfg.storage.root_dir).mkdir(parents=True, exist_ok=True)
        Path(cfg.storage.reports_dir).mkdir(parents=True, exist_ok=True)
        Path(cfg.storage.logs_dir).mkdir(parents=True, exist_ok=True)
        return cfg

    def save(self, path: str) -> None:
        Path(os.path.dirname(path) or ".").mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
