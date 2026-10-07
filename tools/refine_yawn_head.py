"""Reproducible development refinement with a frozen YOLO feature extractor.

Train only the 1280 -> 2 linear layer, select on validation, then lock/export
before reporting test results. Static splits are not a subject-held-out study.
Original weights and the production manifest are never overwritten.
"""
import argparse
import copy
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".cache/ultralytics"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
import torch
from ultralytics import YOLO
from driver_monitor.config import load_config
from driver_monitor.evaluation import classification_metrics, image_samples
from driver_monitor.exporting import export_models
from driver_monitor.models import Classifier, artifact_path, prepare_rgb, prepare_tensor, read_manifest, sha256
from driver_monitor.vision import Vision

CACHE = ROOT / ".cache/yawn_refinement"
CLASSES = ["no_yawn", "yawn"]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def partition(digest):
    bucket = int(digest[:8], 16) % 100
    return "train" if bucket < 70 else "val" if bucket < 85 else "test"


def prepare():
    config = load_config(ROOT / "configs/camera_pc.yaml", manifest=ROOT / "models/manifest.json")
    manifest = read_manifest(config.manifest)
    spec = manifest["classifiers"]["yawn"]
    model = Classifier(config.manifest, "yawn", "torch").model
    features, records, pending, metadata = [], [], [], []
    caught = []
    hook = model.model[-1].linear.register_forward_pre_hook(lambda module, inputs: caught.append(inputs[0].detach().numpy().copy()))
    CACHE.mkdir(parents=True, exist_ok=True)
    def flush():
        if not pending:
            return
        caught.clear()
        with torch.inference_mode():
            model(torch.from_numpy(np.concatenate(pending)))
        values = caught[0]
        for record, vector in zip(metadata, values):
            records.append({**record, "feature": len(features)})
            features.append(vector)
        pending.clear()
        metadata.clear()
    def add(image, record):
        if image is None:
            records.append({**record, "feature": None})
            return
        rgb = prepare_rgb(image, spec)
        pending.append(prepare_tensor(rgb, spec))
        metadata.append({**record, "input_sha256": hashlib.sha256(rgb.tobytes()).hexdigest()})
        if len(pending) == 16:
            flush()
    # A byte-identical legacy test/val image may not enter training.
    legacy = []
    owners = {}
    for split in ("train", "val", "test"):
        for path, label in image_samples(ROOT / "kaggle_output/data/yawn_dataset", split):
            digest = sha256(path)
            owners.setdefault(digest, set()).add(split)
            legacy.append((path, label, split, digest))
    duplicates_removed = 0
    for number, (path, label, split, digest) in enumerate(legacy):
        if split != "test" and "test" in owners[digest] or split == "train" and "val" in owners[digest]:
            duplicates_removed += 1
            continue
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Unreadable dataset image: {path}")
        result = Vision(config).observe(image)
        base = {"path": path.relative_to(ROOT).as_posix(), "label": label, "split": split,
                "source": "legacy", "sha256": digest, "quality": result.quality}
        add(image, {**base, "variant": "full"})
        add(result.crops[2] if result.quality == "usable" else None, {**base, "variant": "face"})
        if split == "train":
            # Grayscale is applied to both yawn classes, preventing color from
            # being a shortcut for the grayscale smile source.
            crop = result.crops[2] if result.quality == "usable" else image
            gray = cv2.cvtColor(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
            add(gray, {**base, "variant": "gray_train"})
        if number % 250 == 0:
            print(f"Legacy crops: {number}/{len(legacy)}", flush=True)
    seen = set(owners)
    for source in ("smiles", "genki"):
        source_path = ROOT / f".cache/{source}/source.json"
        provenance = json.loads(source_path.read_text(encoding="utf-8"))
        for number, sample in enumerate(provenance["samples"]):
            digest = sample["sha256"]
            if digest in seen:
                continue
            seen.add(digest)
            path = source_path.parent / sample["path"]
            if sha256(path) != digest:
                raise ValueError("Smile source checksum mismatch")
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f"Unreadable smile: {path}")
            split = partition(digest)
            base = {"path": path.relative_to(ROOT).as_posix(), "label": "no_yawn", "split": split,
                    "source": source, "sha256": digest, "variant": "smile"}
            if source == "genki":
                result = Vision(config).observe(image)
                base["quality"] = result.quality
                # Use the runtime face crop whenever geometry is available;
                # direct fallback is marked and reported separately.
                if result.crops is not None:
                    image = result.crops[2]
            else:
                base["quality"] = "pre_cropped_64px"
            add(image, base)
            if number % 500 == 0:
                print(f"{source} features: {number}/{len(provenance['samples'])}", flush=True)
    flush()
    hook.remove()
    matrix = np.stack(features).astype(np.float32)
    np.savez_compressed(CACHE / "features.npz", features=matrix)
    save(CACHE / "records.json", {"records": records, "config_sha256": config.fingerprint(),
         "baseline_sha256": spec["artifacts"]["torch"]["sha256"], "manifest_sha256": sha256(config.manifest),
         "features_sha256": sha256(CACHE / "features.npz"), "duplicates_removed": duplicates_removed,
         "smile_sources": {s: sha256(ROOT / f".cache/{s}/source.json") for s in ("smiles", "genki")},
         "subject_independence": "unknown; legacy splits and hash-partitioned smile development data"})
    print(json.dumps({"feature_shape": list(matrix.shape), "duplicates_removed": duplicates_removed,
                      "counts": dict(Counter(f"{r['source']}/{r['split']}/{r['variant']}" for r in records))}), flush=True)


def metrics(records, probabilities, split):
    result = {}
    for variant in ("face", "full"):
        rows = [r for r in records if r["source"] == "legacy" and r["split"] == split and r["variant"] == variant]
        truth = [r["label"] for r in rows]
        predicted = [CLASSES[int(probabilities[r["feature"]].argmax())] if r["feature"] is not None else "UNKNOWN" for r in rows]
        result[f"legacy_{variant}"] = classification_metrics(truth, predicted, CLASSES)
        yawns = [r for r in rows if r["label"] == "yawn"]
        result[f"legacy_{variant}"]["yawn_recall_at_070"] = float(sum(r["feature"] is not None and probabilities[r["feature"], 1] >= .7 for r in yawns) / max(len(yawns), 1))
    for source in ("smiles", "genki"):
        rows = [r for r in records if r["source"] == source and r["split"] == split]
        result[source] = {"samples": len(rows),
                         "false_yawn_at_050": int(sum(probabilities[r["feature"], 1] >= .5 for r in rows)),
                         "false_yawn_at_070": int(sum(probabilities[r["feature"], 1] >= .7 for r in rows)),
                         "false_positive_rate_at_070": float(sum(probabilities[r["feature"], 1] >= .7 for r in rows) / max(len(rows), 1))}
        usable = [r for r in rows if r["quality"] == "usable"]
        result[source]["runtime_usable_faces"] = len(usable)
        result[source]["runtime_usable_false_yawn_at_070"] = int(sum(probabilities[r["feature"], 1] >= .7 for r in usable))
    return result


def train(output):
    manifest_path = ROOT / "models/manifest.json"
    provenance = json.loads((CACHE / "records.json").read_text())
    if provenance["manifest_sha256"] != sha256(manifest_path) or provenance["features_sha256"] != sha256(CACHE / "features.npz"):
        raise ValueError("Stale feature cache; run prepare again")
    # Reject duplicated model inputs across splits even when JPEG byte hashes
    # differ; remove all variants of the lower-priority original image.
    raw_records = provenance["records"]
    priority = {"train": 0, "val": 1, "test": 2}
    input_splits = {}
    for row in raw_records:
        if row.get("input_sha256"):
            digest = row["input_sha256"]
            input_splits[digest] = max(input_splits.get(digest, -1), priority[row["split"]])
    excluded = {r["path"] for r in raw_records if r.get("input_sha256") and
                priority[r["split"]] < input_splits[r["input_sha256"]]}
    records = [r for r in raw_records if r["path"] not in excluded]
    provenance["cross_split_duplicate_images_excluded"] = sorted(excluded)
    features = torch.from_numpy(np.load(CACHE / "features.npz")["features"])
    spec = read_manifest(manifest_path)["classifiers"]["yawn"]
    loaded = YOLO(str(artifact_path(manifest_path, spec["artifacts"]["torch"])))
    loaded.model.cpu().float().eval()
    original = copy.deepcopy(loaded.model.model[-1].linear)
    for parameter in original.parameters():
        parameter.requires_grad_(False)
    with torch.no_grad():
        baseline_p = torch.softmax(original(features), 1).numpy()
    baseline = metrics(records, baseline_p, "val")
    rows = [r for r in records if r["split"] == "train" and r["feature"] is not None]
    groups = Counter((r["source"], r["label"]) for r in rows)
    indexes = torch.tensor([r["feature"] for r in rows])
    targets = torch.tensor([CLASSES.index(r["label"]) for r in rows])
    weights = torch.tensor([1 / groups[r["source"], r["label"]] for r in rows])
    weights /= weights.sum()
    x = features[indexes]
    selected, trials, best = None, [], -float("inf")
    for regularization in (0.0, .001, .01, .1):
        head = copy.deepcopy(original)
        for parameter in head.parameters():
            parameter.requires_grad_(True)
        optimizer = torch.optim.Adam(head.parameters(), lr=.005)
        for epoch in range(1, 201):
            optimizer.zero_grad(set_to_none=True)
            loss = (torch.nn.functional.cross_entropy(head(x), targets, reduction="none") * weights).sum()
            penalty = sum((p - q).square().sum() for p, q in zip(head.parameters(), original.parameters()))
            (loss + regularization * penalty).backward()
            optimizer.step()
            if epoch not in (25, 50, 100, 150, 200):
                continue
            with torch.no_grad():
                probabilities = torch.softmax(head(features), 1).numpy()
            val = metrics(records, probabilities, "val")
            qualified = (val["legacy_face"]["per_class"]["yawn"]["f1"] >= max(.85, baseline["legacy_face"]["per_class"]["yawn"]["f1"] - .02)
                         and val["legacy_face"]["yawn_recall_at_070"] >= baseline["legacy_face"]["yawn_recall_at_070"] - .02
                         and val["legacy_full"]["macro_f1"] >= baseline["legacy_full"]["macro_f1"] - .02)
            score = (val["legacy_face"]["macro_f1"] + (1 - val["smiles"]["false_positive_rate_at_070"])
                     + (1 - val["genki"]["false_positive_rate_at_070"])) / 3
            trial = {"regularization": regularization, "epoch": epoch, "score": score,
                     "preserves_validation_yawns": bool(qualified), "metrics": val}
            trials.append(trial)
            print(json.dumps({k: v for k, v in trial.items() if k != "metrics"}), flush=True)
            if qualified and score > best:
                best, selected = score, (copy.deepcopy(head.state_dict()), trial)
    output.mkdir(parents=True, exist_ok=True)
    save(output / "validation.json", {"baseline": baseline, "trials": trials, "selected": selected[1] if selected else None})
    if selected is None:
        raise RuntimeError("No head preserves validation yawn performance; production model unchanged")
    loaded.model.model[-1].linear.load_state_dict(selected[0])
    loaded.ckpt["train_metrics"] = {}
    loaded.ckpt["train_results"] = {}
    loaded.ckpt["epoch"] = selected[1]["epoch"]
    loaded.ckpt["refinement"] = {"method": "frozen backbone and classifier convolution; train final linear only",
        "baseline_sha256": provenance["baseline_sha256"], "records_sha256": sha256(CACHE / "records.json"),
        "selection": "validation only; no test selection", "regularization": selected[1]["regularization"]}
    checkpoint = output / "best_yawn.pt"
    loaded.save(checkpoint)
    # Lock weights and manifest before reading any test metric.
    detector = read_manifest(manifest_path)["detector"]
    detector["file"] = os.path.relpath(artifact_path(manifest_path, detector), output).replace(os.sep, "/")
    save(output / "yunet.source.json", detector)
    exported = export_models(output, artifact_path(manifest_path, read_manifest(manifest_path)["classifiers"]["eye"]["artifacts"]["torch"]), checkpoint)
    contract = read_manifest(exported)
    contract["deployment_validation"] = "smile development refinement; cabin video and Radxa hardware pending"
    contract["refinement"] = loaded.ckpt["refinement"]
    save(exported, contract)
    locked = Classifier(exported, "yawn", "torch").model.model[-1].linear
    with torch.no_grad():
        candidate_p = torch.softmax(locked(features), 1).numpy()
    report = {"type": "static_smile_development_evaluation", "manifest_sha256": sha256(exported),
              "checkpoint_sha256": sha256(checkpoint), "provenance": {k:v for k,v in provenance.items() if k != "records"},
              "selected_on_validation": selected[1], "test_baseline": metrics(records, baseline_p, "test"),
              "test_candidate": metrics(records, candidate_p, "test"),
              "cabin_event_acceptance": "not measured; subjects unknown; hash/image splits do not prove subject independence"}
    save(output / "evaluation.json", report)
    print(json.dumps({k:report[k] for k in ("test_baseline", "test_candidate")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "train"))
    parser.add_argument("--output", type=Path, default=ROOT / "models/smile_refined")
    args = parser.parse_args()
    torch.set_num_threads(2)
    torch.manual_seed(42)
    if args.stage == "prepare":
        prepare()
    else:
        train(args.output.resolve())
