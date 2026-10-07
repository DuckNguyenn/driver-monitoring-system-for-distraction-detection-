"""Validate relocation, checksums and CPU inference from the actual delivery ZIP."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver_monitor.config import ROOT
from driver_monitor.models import sha256

parser = argparse.ArgumentParser()
parser.add_argument("--bundle", default=str(ROOT / "dist/driver-monitor-rock4d.zip"))
args = parser.parse_args()
archive = Path(args.bundle).resolve()
with tempfile.TemporaryDirectory(prefix="bundle_check_", dir=ROOT / "reports") as temporary:
    root = Path(temporary).resolve()
    if not root.is_relative_to(ROOT / "reports"):
        raise RuntimeError("bundle check directory outside workspace")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        for name in names:
            if not (root / name).resolve().is_relative_to(root):
                raise ValueError("unsafe ZIP member")
            if ".venv" in name or "__pycache__" in name or name.endswith((".avi", ".mp4")):
                raise ValueError("unexpected environment/cache/video in delivery")
        if bundle.testzip() is not None:
            raise ValueError("corrupt ZIP member")
        bundle.extractall(root)
    manifest_path = root / "models/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    status = json.loads((root / "BUNDLE_STATUS.json").read_text())
    artifacts = [manifest["detector"]] + [artifact for s in manifest["classifiers"].values() for artifact in s["artifacts"].values()]
    for artifact in artifacts:
        path = (manifest_path.parent / artifact["file"]).resolve()
        if not path.is_relative_to(root) or sha256(path) != artifact["sha256"]:
            raise ValueError("model path/checksum is not portable")
    smoke = None
    if all("onnx" in spec["artifacts"] for spec in manifest["classifiers"].values()):
        code = "from driver_monitor.config import Config; from driver_monitor.models import Classifier; import numpy as np,json; c=Config(); models=[Classifier(c.manifest,n,'onnx') for n in ('eye','yawn')]; print(json.dumps([m.predict(np.zeros((224,224,3),np.uint8)) for m in models])); [m.close() for m in models]"
        result = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        smoke = json.loads(result.stdout)
        if not all(abs(sum(row.values()) - 1) < .0001 for row in smoke):
            raise ValueError("invalid CPU inference probabilities")
    report = {"bundle": str(archive.relative_to(ROOT)), "sha256": sha256(archive), "bytes": archive.stat().st_size,
              "files": len(names), "backend": status["backend"], "relocation_checksums_passed": True,
              "onnx_smoke": smoke, "npu_inference_tested": False, "physical_board_tested": False}
    output = ROOT / "reports" / f"bundle_verification_{status['backend']}.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
