"""Read-only host/board inventory and deployment prerequisites."""
import glob
import importlib.metadata
import json
import platform
from pathlib import Path
from .evaluation import save_report
from .models import artifact_path, read_manifest, sha256


def preflight_report(config, output):
    versions = {}
    for name in ("numpy", "opencv-python", "Pillow", "PyYAML", "pyserial", "torch", "ultralytics", "onnxruntime", "rknn-toolkit2", "rknn-toolkit-lite2"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    system = {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version(), "kernel": platform.release()}
    for name, path in (("os_release", "/etc/os-release"), ("board_model", "/proc/device-tree/model"), ("board_compatible", "/proc/device-tree/compatible"), ("npu_driver", "/sys/kernel/debug/rknpu/version")):
        try:
            system[name] = Path(path).read_text().replace("\x00", " ").strip()
        except (OSError, UnicodeError):
            system[name] = None
    try:
        import psutil
        system["ram_bytes"] = psutil.virtual_memory().total
    except ImportError:
        system["ram_bytes"] = None
    checks = {}
    try:
        manifest = read_manifest(config.manifest)
        for name, spec in manifest["classifiers"].items():
            try:
                artifact_path(config.manifest, spec["artifacts"][config.backend])
                checks[name] = "checksum_ok"
            except (ValueError, OSError, KeyError) as exc:
                checks[name] = str(exc)
        artifact_path(config.manifest, manifest["detector"])
        checks["yunet"] = "checksum_ok"
    except (OSError, ValueError, KeyError) as exc:
        checks["manifest"] = str(exc)
    if config.auto_glasses:
        from .eyewear import read_eyewear_manifest
        for name, path in (("eyewear_selector", config.eyewear_manifest), ("eye_glasses", config.glasses_eye_manifest)):
            try:
                spec = (read_eyewear_manifest(path)["classifier"]["artifact"] if name == "eyewear_selector"
                        else read_manifest(path)["classifiers"]["eye"]["artifacts"][config.backend])
                artifact_path(path, spec)
                checks[name] = "checksum_ok"
            except (OSError, ValueError, KeyError) as exc:
                checks[name] = str(exc)
    board_matches = "rk3576" in (system.get("board_compatible") or "").lower()
    runtime_libraries = {}
    for path in ("/usr/lib/librknnrt.so", "/usr/lib/aarch64-linux-gnu/librknnrt.so", "/usr/local/lib/librknnrt.so"):
        if Path(path).is_file():
            runtime_libraries[path] = sha256(path)
    report = {"system": system, "versions": versions, "backend": config.backend, "model_checks": checks,
              "video_devices": glob.glob("/dev/video*"), "serial_devices": glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"),
              "rock4d_matches": board_matches, "npu_inference_validated": False,
              "runtime_library_sha256": runtime_libraries,
              "note": "Inventory only. NPU inference, FPS, buzzer and accuracy require hardware tests."}
    save_report(output, report)
    return report
