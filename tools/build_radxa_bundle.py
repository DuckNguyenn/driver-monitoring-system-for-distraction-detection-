"""Create a portable software bundle; require actual RKNN artifacts for NPU mode."""
import argparse
import copy
import json
from pathlib import Path
import sys
import zipfile
from dataclasses import asdict
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver_monitor.config import ROOT, load_config
from driver_monitor.models import artifact_path, read_manifest

parser = argparse.ArgumentParser()
parser.add_argument("--backend", choices=("onnx", "rknn"), default="onnx")
parser.add_argument("--manifest", help="override the model manifest selected by --config")
parser.add_argument("--config", default=str(ROOT / "configs/driver_monitor.yaml"), help="preserve this profile's crop and temporal thresholds")
parser.add_argument("--output", default=str(ROOT / "dist/driver-monitor-rock4d.zip"))
args = parser.parse_args()
source_config_path = Path(args.config).resolve()
source_config = load_config(source_config_path, manifest=args.manifest, backend=args.backend)
if source_config.auto_glasses:
    raise SystemExit("Automatic glasses assets are not included by this packager; package the base profile first")
manifest_path = source_config.manifest
manifest = copy.deepcopy(read_manifest(manifest_path))
manifest_origin = manifest_path.relative_to(ROOT).as_posix() if manifest_path.is_relative_to(ROOT) else manifest_path.name
detector = manifest["detector"]
artifacts = [(artifact_path(manifest_path, detector), "models/" + Path(detector["file"]).name)]
detector["file"] = Path(detector["file"]).name
for name, spec in manifest["classifiers"].items():
    if args.backend not in spec["artifacts"]:
        raise SystemExit(f"{name}: {args.backend} artifact missing; convert first")
    selected = spec["artifacts"][args.backend]
    packaged = name + Path(selected["file"]).suffix
    artifacts.append((artifact_path(manifest_path, selected), "models/" + packaged))
    spec["artifacts"] = {args.backend: {**selected, "file": packaged}}
    if args.backend == "rknn":
        reference = read_manifest(manifest_path)["classifiers"][name]["artifacts"]["onnx"]
        artifacts.append((artifact_path(manifest_path, reference), "models/" + name + ".onnx"))
        spec["artifacts"]["onnx"] = {**reference, "file": name + ".onnx"}
path = Path(args.output).resolve()
path.parent.mkdir(parents=True, exist_ok=True)
web = ROOT / "frontend/web/dist"
if not (web / "index.html").exists():
    raise SystemExit("Build the dashboard with npm run build:web before packaging")
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
    # Only templates/protocols from data_collection; never package personal clips or crops.
    for folder in ("driver_monitor", "scripts", "radxa_rock4d/systemd", "esp32_buzzer"):
        for file in (ROOT / folder).rglob("*"):
            if file.is_file() and "__pycache__" not in file.parts:
                bundle.write(file, file.relative_to(ROOT).as_posix())
    for file in web.rglob("*"):
        if file.is_file():
            bundle.write(file, file.relative_to(ROOT).as_posix())
    for name in ("README_DRIVER_MONITOR.md", "DEPLOY_RADXA.md", "DASHBOARD.md", "requirements-dashboard.txt", "requirements-dashboard.lock.txt", "requirements-runtime.txt", "models/yunet.source.json", "models/yunet.LICENSE", "models/README.md",
                 "data_collection/README.md", "data_collection/annotations.template.csv", "tools/probe_camera.py", "tools/record_camera.py", "tools/test_esp32.py",
                 "radxa_rock4d/rknn_conversion/requirements-host.txt", "reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.pdf", "reports/software_verification.json"):
        file = ROOT / name
        bundle.write(file, name)
    config = asdict(source_config)
    config.update(manifest="../models/manifest.json", log_dir="../logs", backend=args.backend,
                  headless=True, serial_port=None, realtime=False, max_frames=0)
    for key in ("auto_glasses", "eyewear_manifest", "glasses_eye_manifest"):
        config.pop(key)
    portable_config = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
    bundle.writestr("configs/driver_monitor.yaml", portable_config)
    bundle.writestr("configs/camera_pc.yaml", portable_config)
    bundle.writestr("models/manifest.json", json.dumps(manifest, indent=2))
    for file, destination in artifacts:
        bundle.write(file, destination)
    bundle.writestr("BUNDLE_STATUS.json", json.dumps({"backend": args.backend, "board_tested": False, "source_manifest": manifest_origin, "dashboard_web_built": True,
                   "source_config": source_config_path.relative_to(ROOT).as_posix() if source_config_path.is_relative_to(ROOT) else source_config_path.name,
                   "config_sha256": source_config.fingerprint(), "automatic_glasses_included": False,
                   "note": "Software bundle. Preflight and hardware acceptance are still required."}, indent=2))
    if (ROOT / "reports/rknn_conversion.json").exists():
        bundle.write(ROOT / "reports/rknn_conversion.json", "reports/rknn_conversion.json")
    if (ROOT / "reports/rknn_simulator_smoke.json").exists():
        bundle.write(ROOT / "reports/rknn_simulator_smoke.json", "reports/rknn_simulator_smoke.json")
    for name in ("reports/dashboard_verification/latest.json", "reports/dashboard_verification/web-browser.json"):
        if (ROOT / name).exists():
            bundle.write(ROOT / name, name)
    bundle.writestr("BUNDLE_README.txt", "Portable software/model package for ROCK 4D.\nStart with DEPLOY_RADXA.md and BUNDLE_STATUS.json.\nPhysical board, camera, buzzer and accuracy acceptance remain pending.\nDetailed PC logs, videos, original checkpoints and datasets referenced by documents remain in the original workspace and are not included in this package.\n")
print(path)
