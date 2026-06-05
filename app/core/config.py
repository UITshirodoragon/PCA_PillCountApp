from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path


POSTPROCESS_FIELDS = (
    "threshold",
    "nms_ksize",
    "min_peak",
    "max_peaks",
    "realtime_fps",
    "torch_num_threads",
    "smoothing_alpha",
    "count_queue_window",
    "count_queue_min_votes",
    "roi_enabled",
    "roi_x",
    "roi_y",
    "roi_w",
    "roi_h",
)


def default_postprocess_profiles() -> dict:
    return {
        "PANetBase": {
            "threshold": 0.5,
            "nms_ksize": 5,
            "min_peak": 0.4,
            "max_peaks": 500,
            "realtime_fps": 6,
            "torch_num_threads": 1,
            "smoothing_alpha": 0.2,
            "count_queue_window": 7,
            "count_queue_min_votes": 2,
            "roi_enabled": False,
            "roi_x": 32,
            "roi_y": 16,
            "roi_w": 280,
            "roi_h": 208,
        },
        "PANetNano": {
            "threshold": 0.45,
            "nms_ksize": 5,
            "min_peak": 0.25,
            "max_peaks": 500,
            "realtime_fps": 6,
            "torch_num_threads": 1,
            "smoothing_alpha": 0.15,
            "count_queue_window": 5,
            "count_queue_min_votes": 2,
            "roi_enabled": False,
            "roi_x": 32,
            "roi_y": 16,
            "roi_w": 280,
            "roi_h": 208,
        },
    }


@dataclass
class CameraSettings:
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    profile: str = "balanced"  # fast | balanced | quality | custom
    lock_controls: bool = True
    auto_exposure_value: float = 1.0
    exposure: float = 156.0
    gain: float = 0.0
    lock_white_balance: bool = True
    white_balance_temperature: int = 4500


@dataclass
class ModelSettings:
    runtime: str = "pytorch"
    model_path: str = "./Networks/weights/model_best_nano.pth"
    onnx_model_path: str = "./Networks/weights/model_best_nano.onnx"
    model_arch: str = "PANetNano"
    threshold: float = 0.4
    nms_ksize: int = 5
    min_peak: float = 0.25
    max_peaks: int = 500
    realtime_fps: int = 6
    torch_num_threads: int = 1
    smoothing_alpha: float = 0.0
    count_queue_window: int = 7
    count_queue_min_votes: int = 3
    roi_enabled: bool = True
    roi_x: int = 32
    roi_y: int = 16
    roi_w: int = 280
    roi_h: int = 208
    postprocess_profiles: dict = field(default_factory=default_postprocess_profiles)

    def postprocess_dict(self) -> dict:
        return {k: copy.deepcopy(getattr(self, k)) for k in POSTPROCESS_FIELDS}

    def set_postprocess_dict(self, profile: dict) -> None:
        profile = profile or {}
        for k in POSTPROCESS_FIELDS:
            if k in profile:
                setattr(self, k, copy.deepcopy(profile[k]))

    def ensure_postprocess_profiles(self, preserve_flat_settings: bool = False) -> None:
        defaults = default_postprocess_profiles()
        profiles = copy.deepcopy(defaults)
        for arch, profile in (self.postprocess_profiles or {}).items():
            base = profiles.get(arch, {})
            base.update(profile or {})
            profiles[arch] = base
        self.postprocess_profiles = profiles

        if preserve_flat_settings:
            self.postprocess_profiles[self.model_arch] = self.postprocess_dict()

    def apply_postprocess_profile(self, arch: str | None = None) -> None:
        arch = arch or self.model_arch
        self.ensure_postprocess_profiles(False)
        profile = self.postprocess_profiles.get(arch)
        if profile:
            self.set_postprocess_dict(profile)

    def update_postprocess_profile(self, arch: str | None = None, profile: dict | None = None) -> None:
        arch = arch or self.model_arch
        self.ensure_postprocess_profiles(False)
        self.postprocess_profiles[arch] = copy.deepcopy(profile or self.postprocess_dict())


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

        model_data = data.get("model", {})
        cfg = AppConfig(
            camera=_load_dc(CameraSettings, data.get("camera", {})),
            model=_load_dc(ModelSettings, model_data),
            serial=_load_dc(SerialSettings, data.get("serial", {})),
            share=_load_dc(ShareSettings, data.get("share", {})),
            cloudflare=_load_dc(CloudflareSettings, data.get("cloudflare", {})),
            storage=_load_dc(StorageSettings, data.get("storage", {})),
        )
        cfg.model.ensure_postprocess_profiles("postprocess_profiles" not in (model_data or {}))
        cfg.model.apply_postprocess_profile(cfg.model.model_arch)

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
