"""Strict configuration with paths relative to the configuration file."""
from dataclasses import asdict, dataclass, field
from pathlib import Path
import hashlib
import json

from .core import MonitorConfig


ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    manifest: Path = ROOT / "models/manifest.json"
    log_dir: Path = ROOT / "logs"
    backend: str = "onnx"
    width: int = 640
    height: int = 480
    detector_size: int = 320
    detector_confidence: float = 0.8
    driver_roi: tuple = (0.0, 0.0, 1.0, 1.0)
    eye_width_ratio: float = 0.8
    eye_height_ratio: float = 0.6
    face_margin: float = 0.10
    eye_motion_window_seconds: float = 0.30
    eye_motion_settle_seconds: float = 0.35
    eye_motion_max_shift_ratio: float = 0.08
    eye_motion_max_roll_degrees: float = 3.0
    min_face_size: int = 80
    min_eye_width: int = 12
    min_brightness: float = 25.0
    min_sharpness: float = 20.0
    # Older configs use min_sharpness for both face and eyes.
    min_eye_sharpness: float | None = None
    max_overexposed_ratio: float = 0.6
    serial_port: str | None = None
    serial_baud: int = 115200
    headless: bool = True
    realtime: bool = False
    max_frames: int = 0
    cpu_threads: int = 2
    rotation_degrees: int = 0
    auto_glasses: bool = False
    eyewear_manifest: str | Path = str(ROOT / "models/eyewear_selector/manifest.json")
    glasses_eye_manifest: str | Path = str(ROOT / "models/eye_glasses_adapted/manifest.json")
    monitor: MonitorConfig = field(default_factory=MonitorConfig)

    def __post_init__(self):
        if self.min_eye_sharpness is None:
            self.min_eye_sharpness = self.min_sharpness
        if not isinstance(self.auto_glasses, bool):
            raise ValueError("auto_glasses must be a boolean")
        # New optional paths stay YAML-safe in existing exporters using asdict.
        self.eyewear_manifest = str(Path(self.eyewear_manifest).resolve())
        self.glasses_eye_manifest = str(Path(self.glasses_eye_manifest).resolve())
        if self.backend not in ("torch", "onnx", "rknn"):
            raise ValueError("backend must be torch, onnx or rknn")
        if self.rotation_degrees not in (0, 90, 180, 270):
            raise ValueError("rotation_degrees must be 0, 90, 180 or 270")
        for name in ("width", "height", "detector_size", "min_face_size", "min_eye_width", "serial_baud", "cpu_threads"):
            if not isinstance(getattr(self, name), int) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.headless, bool) or not isinstance(self.realtime, bool) or not isinstance(self.max_frames, int) or self.max_frames < 0:
            raise ValueError("invalid headless/max_frames")
        x1, y1, x2, y2 = self.driver_roi
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("driver_roi must be normalized [x1,y1,x2,y2]")
        for name in ("eye_width_ratio", "eye_height_ratio", "min_brightness", "min_sharpness", "min_eye_sharpness",
                     "eye_motion_window_seconds", "eye_motion_settle_seconds", "eye_motion_max_shift_ratio", "eye_motion_max_roll_degrees"):
            if not 0 < getattr(self, name) < float("inf"):
                raise ValueError(f"invalid {name}")
        if not 0 <= self.face_margin <= 1 or not 0 < self.detector_confidence <= 1 or not 0 <= self.max_overexposed_ratio <= 1:
            raise ValueError("invalid vision thresholds")
        if self.eye_motion_max_shift_ratio > 1 or self.eye_motion_max_roll_degrees > 90:
            raise ValueError("invalid eye motion limits")

    def fingerprint(self):
        values = asdict(self)
        for key in ("auto_glasses", "eyewear_manifest", "glasses_eye_manifest"):
            values.pop(key)
        if self.auto_glasses:
            from .eyewear import read_eyewear_manifest
            from .models import read_manifest
            selector = read_eyewear_manifest(self.eyewear_manifest)
            specialist = read_manifest(self.glasses_eye_manifest)["classifiers"]["eye"]
            values["auto_glasses"] = {"selector": selector, "specialist": {
                "classes": specialist["classes"], "preprocessing": specialist["preprocessing"],
                "sha256": specialist["artifacts"].get(self.backend, {}).get("sha256")}}
        for key in ("manifest", "log_dir", "headless", "realtime", "max_frames", "serial_port", "serial_baud", "cpu_threads"):
            values.pop(key)
        if self.manifest.exists():
            manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
            values["models"] = {name: {"classes": spec["classes"], "preprocessing": spec["preprocessing"],
                                       "sha256": spec["artifacts"].get(self.backend, {}).get("sha256")}
                                for name, spec in manifest["classifiers"].items()}
            for name, spec in manifest["classifiers"].items():
                values["models"][name].update({key: spec[key] for key in ("inference_views", "view_aggregation") if key in spec})
            values["detector_sha256"] = manifest["detector"]["sha256"]
        return hashlib.sha256(json.dumps(values, default=str, sort_keys=True).encode()).hexdigest()


def load_config(path=None, **overrides):
    values = {}
    base = ROOT
    if path:
        import yaml
        path = Path(path).resolve()
        base = path.parent
        values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(values, dict):
            raise ValueError("configuration must be a mapping")
    monitor = values.pop("monitor", {})
    if not isinstance(monitor, dict):
        raise ValueError("monitor must be a mapping")
    for key in ("manifest", "log_dir", "eyewear_manifest", "glasses_eye_manifest"):
        if key in values:
            values[key] = (base / values[key]).resolve()
    # CLI paths follow the caller's working directory, YAML paths the YAML directory.
    for key, value in overrides.items():
        if value is not None:
            values[key] = Path(value).resolve() if key in ("manifest", "log_dir", "eyewear_manifest", "glasses_eye_manifest") else value
    if "driver_roi" in values:
        values["driver_roi"] = tuple(values["driver_roi"])
    return Config(**values, monitor=MonitorConfig(**monitor))
