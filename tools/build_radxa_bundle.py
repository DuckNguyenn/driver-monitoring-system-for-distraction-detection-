"""Create a portable software bundle; require actual RKNN artifacts for NPU mode."""
import argparse
import copy
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver_monitor.config import ROOT
from driver_monitor.models import artifact_path, read_manifest

parser = argparse.ArgumentParser()
parser.add_argument("--backend", choices=("onnx", "rknn"), default="onnx")
parser.add_argument("--output", default=str(ROOT / "dist/driver-monitor-rock4d.zip"))
args = parser.parse_args()
manifest_path = ROOT / "models/manifest.json"
manifest = copy.deepcopy(read_manifest(manifest_path))
artifacts = [(artifact_path(manifest_path, manifest["detector"]), "models/" + manifest["detector"]["file"])]
for name, spec in manifest["classifiers"].items():
    if args.backend not in spec["artifacts"]:
        raise SystemExit(f"{name}: {args.backend} artifact missing; convert first")
    selected = spec["artifacts"][args.backend]
    artifacts.append((artifact_path(manifest_path, selected), "models/" + Path(selected["file"]).name))
    spec["artifacts"] = {args.backend: {**selected, "file": Path(selected["file"]).name}}
    if args.backend == "rknn":
        reference = read_manifest(manifest_path)["classifiers"][name]["artifacts"]["onnx"]
        artifacts.append((artifact_path(manifest_path, reference), "models/" + Path(reference["file"]).name))
        spec["artifacts"]["onnx"] = {**reference, "file": Path(reference["file"]).name}
path = Path(args.output).resolve()
path.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
    # Only templates/protocols from data_collection; never package personal clips or crops.
    for folder in ("driver_monitor", "scripts", "radxa_rock4d/systemd", "esp32_buzzer"):
        for file in (ROOT / folder).rglob("*"):
            if file.is_file() and "__pycache__" not in file.parts:
                bundle.write(file, file.relative_to(ROOT).as_posix())
    for name in ("README_DRIVER_MONITOR.md", "DEPLOY_RADXA.md", "requirements-runtime.txt", "models/yunet.source.json", "models/yunet.LICENSE", "models/README.md",
                 "data_collection/README.md", "data_collection/annotations.template.csv", "tools/probe_camera.py", "tools/record_camera.py", "tools/test_esp32.py",
                 "radxa_rock4d/rknn_conversion/requirements-host.txt", "reports/IMPLEMENTATION_REPORT.md", "reports/software_verification.json"):
        file = ROOT / name
        bundle.write(file, name)
    config = (ROOT / "configs/driver_monitor.yaml").read_text(encoding="utf-8").replace("backend: onnx", f"backend: {args.backend}")
    bundle.writestr("configs/driver_monitor.yaml", config)
    bundle.writestr("models/manifest.json", json.dumps(manifest, indent=2))
    for file, destination in artifacts:
        bundle.write(file, destination)
    bundle.writestr("BUNDLE_STATUS.json", json.dumps({"backend": args.backend, "board_tested": False,
                   "note": "Software bundle. Preflight and hardware acceptance are still required."}, indent=2))
    if (ROOT / "reports/rknn_conversion.json").exists():
        bundle.write(ROOT / "reports/rknn_conversion.json", "reports/rknn_conversion.json")
    if (ROOT / "reports/rknn_simulator_smoke.json").exists():
        bundle.write(ROOT / "reports/rknn_simulator_smoke.json", "reports/rknn_simulator_smoke.json")
    bundle.writestr("BUNDLE_README.txt", "Portable software/model package for ROCK 4D.\nStart with DEPLOY_RADXA.md and BUNDLE_STATUS.json.\nPhysical board, camera, buzzer and accuracy acceptance remain pending.\nDetailed PC logs, videos, original checkpoints and datasets referenced by documents remain in the original workspace and are not included in this package.\n")
print(path)
