"""Verify held-out smiles with real pixel preprocessing and exported models."""
import json
import sys
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from driver_monitor.config import load_config
from driver_monitor.models import Classifier, sha256
from driver_monitor.vision import Vision


def main():
    config = load_config(ROOT / "configs/camera_pc.yaml")
    evaluation = json.loads((ROOT / "models/smile_refined/evaluation.json").read_text())
    excluded = set(evaluation["provenance"]["cross_split_duplicate_images_excluded"])
    records = json.loads((ROOT / ".cache/yawn_refinement/records.json").read_text())["records"]
    rows = [r for r in records if r["split"] == "test" and r["source"] in ("smiles", "genki") and r["path"] not in excluded]
    baseline = Classifier(ROOT / "models/manifest.json", "yawn", "onnx")
    candidate = Classifier(config.manifest, "yawn", "onnx")
    torch_model = Classifier(config.manifest, "yawn", "torch")
    predictions, error, agreement = [], 0., 0
    try:
        for row in rows:
            path = ROOT / row["path"]
            if sha256(path) != row["sha256"]:
                raise ValueError("Source image checksum mismatch")
            image = cv2.imread(str(path))
            quality = row["quality"]
            if row["source"] == "genki":
                result = Vision(config).observe(image)
                if result.quality != quality:
                    raise ValueError("Changed detector/crop/quality configuration")
                if result.crops is not None:
                    image = result.crops[2]
            old = baseline.predict(image)
            new = candidate.predict(image)
            expected = torch_model.predict(image)
            error = max(error, abs(new["yawn"] - expected["yawn"]))
            agreement += max(new, key=new.get) == max(expected, key=expected.get)
            predictions.append({"path": row["path"], "source": row["source"], "sha256": row["sha256"],
                "quality": quality, "baseline_yawn": old["yawn"], "candidate_yawn": new["yawn"]})
    finally:
        for model in (baseline, candidate, torch_model):
            model.close()
    summary = {}
    for source in ("smiles", "genki"):
        selected = [r for r in predictions if r["source"] == source]
        usable = [r for r in selected if r["quality"] == "usable"]
        summary[source] = {"samples": len(selected),
            "baseline_false_yawn_ge_070": sum(r["baseline_yawn"] >= .7 for r in selected),
            "candidate_false_yawn_ge_070": sum(r["candidate_yawn"] >= .7 for r in selected),
            "runtime_usable_faces": len(usable),
            "baseline_false_yawn_usable_ge_070": sum(r["baseline_yawn"] >= .7 for r in usable),
            "candidate_false_yawn_usable_ge_070": sum(r["candidate_yawn"] >= .7 for r in usable)}
    report = {"type": "held_out_static_smile_pixels", "summary": summary,
        "manifest_sha256": sha256(config.manifest), "config_sha256": config.fingerprint(),
        "parity": {"maximum_probability_error": error, "label_agreement": agreement / len(predictions)},
        "subject_independence": "unknown; development evaluation", "predictions": predictions}
    (ROOT / "reports/smile_refinement_pixels.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "predictions"}), flush=True)


if __name__ == "__main__":
    main()
