"""Replay pinned smiling face crops through the deployed classifier and monitor."""
import argparse
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from driver_monitor import Monitor, MonitorConfig, Observation
from driver_monitor.config import load_config
from driver_monitor.models import Classifier, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=load_config(ROOT / "configs/camera_pc.yaml").manifest)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/smiles/source.json")
    parser.add_argument("--backend", default="onnx", choices=("onnx", "torch"))
    args = parser.parse_args()
    samples = json.loads(args.fixtures.read_text(encoding="utf-8"))["samples"]
    model = Classifier(args.manifest, "yawn", args.backend)
    failures = []
    try:
        for sample in samples:
            path = args.fixtures.parent / sample["file"]
            if sha256(path) != sample["sha256"]:
                raise ValueError(f"Smile fixture checksum changed: {path}")
            probabilities = model.predict(cv2.imread(str(path)))
            monitor = Monitor(MonitorConfig(yawn_smoothing_seconds=.2))
            eye = {"Open": .99, "Closed": .01}
            # A held smile must not become a yawn, regardless of smoothing.
            for index in range(31):
                status = monitor.update(Observation(index / 15, eye, eye, probabilities))
            result = {"file": sample["file"], "yawn_probability": probabilities["yawn"],
                      "yawn_count_after_two_seconds": status.yawn_count}
            print(json.dumps(result), flush=True)
            if status.yawn_count:
                failures.append(result)
    finally:
        model.close()
    if failures:
        raise AssertionError(f"{len(failures)} smiling face(s) counted as yawns")
    print("PASS: held smiles do not count as yawns", flush=True)


if __name__ == "__main__":
    main()
