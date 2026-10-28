"""Collect/review -> native runtime crops -> distance-aware yawn fine-tuning.

Validation alone selects weights. Test/locked clips are evaluation-only.
Uses the installed torch/Ultralytics environment, with no training downloads.
"""
import argparse
import copy
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".cache/ultralytics"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))

import cv2
import numpy as np
import yaml

from driver_monitor.capture import Capture
from driver_monitor.config import load_config
from driver_monitor.evaluation import classification_metrics
from driver_monitor.models import artifact_path, prepare_rgb, prepare_tensor, read_manifest, sha256
from driver_monitor.vision import Vision, orient_frame
from driver_monitor.yawn_distance import (CLASSES, DISTANCES, FIELDS, DistanceAugmentation,
    json_save, preview_views, read_distance_annotations, summarize, training_rgb, verify_prepared_dataset)


def options(path):
    path = Path(path).resolve()
    values = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("runtime_config", "annotations", "videos", "dataset", "output", "retained_static_records"):
        if values.get(key):
            values[key] = (path.parent / values[key]).resolve()
    values["options_path"] = path
    values["recipe"] = DistanceAugmentation(**values["augmentation"])
    values["active_distances"] = tuple(values.get("active_distances", DISTANCES))
    values["validation_mode"] = values.get("validation_mode", "camera")
    if (not values["active_distances"] or len(set(values["active_distances"])) != len(values["active_distances"]) or
            any(d not in DISTANCES for d in values["active_distances"])):
        raise ValueError("invalid active distances")
    if values["validation_mode"] not in ("camera", "static_only"):
        raise ValueError("validation_mode must be camera or static_only")
    if values["validation_mode"] == "static_only" and not values.get("retained_static_records"):
        raise ValueError("static_only needs retained static validation records")
    if values["trainable"] != "classifier":
        raise ValueError("this recipe supports classifier fine-tuning only")
    for name in ("batch_size", "epochs", "threads", "max_epoch_samples", "patience"):
        if not isinstance(values[name], int) or values[name] < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not 0 < values["learning_rate"] <= .01 or not 0 < values["camera_weight"] < 1:
        raise ValueError("invalid learning rate/camera weight")
    if not 0 < values["sample_seconds"] <= 1 or values["training_min_face_sharpness"] < 0:
        raise ValueError("invalid sampling/training quality settings")
    return values


def init(o):
    o["videos"].mkdir(parents=True, exist_ok=True)
    if not o["annotations"].exists():
        o["annotations"].parent.mkdir(parents=True, exist_ok=True)
        with o["annotations"].open("x", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(FIELDS)
    print(f"Camera clips: {o['videos']}\nReviewed labels: {o['annotations']}")


def checked_annotations(o):
    return read_distance_annotations(o["annotations"], o["videos"], o["split_mode"],
        active_distances=o["active_distances"], required_splits=camera_splits(o))


def camera_splits(o):
    return ("train",) if o["validation_mode"] == "static_only" else ("train", "val")


def prepare(o):
    annotations = checked_annotations(o)
    config = load_config(o["runtime_config"])
    manifest = read_manifest(config.manifest)
    spec = manifest["classifiers"]["yawn"]
    if spec.get("inference_views", ["center"]) != ["center"]:
        raise ValueError("use a single-view runtime manifest for this recipe")
    output = o["dataset"]
    if output.exists() and any(output.iterdir()):
        raise ValueError("dataset is nonempty; use a new dataset path in YAML")
    output.mkdir(parents=True, exist_ok=True)
    records, sources, groups = [], [], defaultdict(list)
    sources.append({"file": str(o["annotations"]), "sha256": sha256(o["annotations"])})
    for row in annotations:
        groups[row["clip_id"]].append(row)

    def add(crop, metadata):
        row = {**metadata, "file": None, "input_sha256": None, "augmentation": "original"}
        if crop is not None:
            name = f"native/{len(records):07d}.png"
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(destination), crop):
                raise OSError("native crop write failed")
            row.update(file=name, sha256=sha256(destination), native_shape=list(crop.shape),
                       input_sha256=hashlib.sha256(prepare_rgb(crop, spec).tobytes()).hexdigest())
        records.append(row)

    for clip_id, intervals in groups.items():
        clip = o["videos"] / clip_id
        sidecar = clip.with_suffix(".timestamps.json")
        if not sidecar.is_file():
            raise ValueError("distance camera collection requires the exact timestamp sidecar")
        source = json.loads(sidecar.read_text(encoding="utf-8"))
        protocol_path = clip.with_suffix(".protocol.json")
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        collection = protocol.get("collection") or {}
        if (collection.get("runtime_config_sha256") != config.fingerprint() or
                collection.get("manifest_sha256") != sha256(config.manifest)):
            raise ValueError("collection crop/config differs from runtime; record with the configured profile")
        for key in ("subject_id", "capture_group", "split", "distance", "lighting"):
            if collection.get(key) != intervals[0][key]:
                raise ValueError(f"annotation {key} differs from recorded clip metadata")
        if len(source.get("frame_sha256", [])) != len(source["timestamps_seconds"]):
            raise ValueError("distance captures require lossless frame hashes")
        if max(r["end"] for r in intervals) > source["timestamps_seconds"][-1] + .25:
            raise ValueError(f"annotation extends beyond capture: {clip_id}")
        video_digest = sha256(clip)
        sources.extend({"file": str(p), "sha256": sha256(p)} for p in (clip, sidecar, protocol_path))
        vision = Vision(config)
        capture = Capture(clip)
        last = -float("inf")
        try:
            while (packet := capture.read()) is not None:
                if hashlib.sha256(packet.image.tobytes()).hexdigest() != source["frame_sha256"][packet.index]:
                    raise ValueError("raw recording pixels changed")
                result = vision.observe(orient_frame(packet.image, config.rotation_degrees), packet.timestamp)
                if packet.timestamp - last < o["sample_seconds"] - 1e-9:
                    continue
                active = next((r for r in intervals if r["start"] <= packet.timestamp < r["end"]), None)
                if not active:
                    continue
                last = packet.timestamp
                crop = None if result.crops is None else result.crops[2]
                # Real mild blur can train the classifier. Runtime quality remains unchanged.
                sharpness = result.metrics.get("sharpness", 0)
                train_ok = (crop is not None and result.quality in ("usable", "blurry") and
                            sharpness >= o["training_min_face_sharpness"])
                add(crop, {**active, "domain": "camera", "source": clip_id, "timestamp": packet.timestamp,
                    "frame": packet.index, "quality": result.quality, "metrics": result.metrics,
                    "train_eligible": train_ok, "video_sha256": video_digest})
        finally:
            capture.close()
        print(f"Prepared camera clip: {clip_id}", flush=True)

    static_path = o.get("retained_static_records")
    if static_path:
        provenance = json.loads(static_path.read_text(encoding="utf-8"))
        sources.append({"file": str(static_path), "sha256": sha256(static_path)})
        candidates = [r for r in provenance["records"] if r.get("feature") is not None and
            r["variant"] in ("face", "smile") and r["split"] in ("train", "val")]
        # Preserve old test/val owners before sampling static train data.
        owners = defaultdict(set)
        for r in provenance["records"]:
            owners[r["sha256"]].add(r["split"])
        counts = Counter()
        for r in sorted(candidates, key=lambda item: item["sha256"]):
            if r["split"] == "train" and owners[r["sha256"]] - {"train"}:
                continue
            group = (r["split"], r["source"], r["label"])
            limit = o["static_train_per_group"] if r["split"] == "train" else o["static_val_per_group"]
            if counts[group] >= limit:
                continue
            path = ROOT / r["path"]
            if sha256(path) != r["sha256"]:
                raise ValueError("retained static image changed")
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError("retained static image unreadable")
            result = Vision(config).observe(image, 0.) if r["source"] != "smiles" else None
            crop = image if r["source"] == "smiles" else (None if result.crops is None else result.crops[2])
            if crop is None:
                continue
            sources.append({"file": str(path), "sha256": r["sha256"]})
            add(crop, {"domain": "static", "source": r["source"], "split": r["split"],
                "label": r["label"], "action": "normal" if r["source"] == "legacy" else "smile",
                "distance": "unspecified", "subject_id": "legacy_subject_unknown", "quality": "usable",
                "train_eligible": True, "crop_source": "pre_cropped" if result is None else "runtime_yunet"})
            counts[group] += 1

    # A crop identical to val/test cannot survive as a training sibling.
    owners, labels = defaultdict(set), {}
    for row in records:
        digest = row.get("input_sha256")
        if not digest:
            continue
        if digest in labels and labels[digest] != row["label"]:
            raise ValueError("conflicting labels for identical prepared pixels")
        owners[digest].add(row["split"]); labels[digest] = row["label"]
    excluded = [r for r in records if r["split"] == "train" and
                owners[r.get("input_sha256")] - {"train"}]
    records = [r for r in records if r not in excluded]
    for split in camera_splits(o):
        for distance in o["active_distances"]:
            for label in CLASSES:
                usable = [r for r in records if r["domain"] == "camera" and r["split"] == split and
                    r["distance"] == distance and r["label"] == label and r["file"] and
                    (r["train_eligible"] if split == "train" else r["quality"] == "usable")]
                if not usable:
                    raise ValueError(f"no eligible crops for {split}/{distance}/{label}; improve recording conditions")
    if o["validation_mode"] == "static_only":
        static = [r for r in records if r["domain"] == "static" and r["split"] == "val" and r["file"]]
        support = Counter((r["source"], r["label"]) for r in static)
        for source, label in (("legacy", "no_yawn"), ("legacy", "yawn"),
                              ("smiles", "no_yawn"), ("genki", "no_yawn")):
            if support[source, label] < 10:
                raise ValueError(f"insufficient static validation: {source}/{label}")
    data = {"schema_version": 1, "records": records, "sources": sources,
        "runtime_config_sha256": config.fingerprint(), "manifest_sha256": sha256(config.manifest),
        "augmentation": asdict(o["recipe"]), "annotations_sha256": sha256(o["annotations"]),
        "camera_split_mode": o["split_mode"], "static_subject_independence": "unknown",
        "active_distances": list(o["active_distances"]), "validation_mode": o["validation_mode"],
        "independent_camera_validation_available": o["validation_mode"] == "camera",
        "excluded_duplicate_training_crops": len(excluded), "runtime_spec": spec,
        "coverage": summarize([r for r in records if r["domain"] == "camera"])}
    json_save(output / "dataset.json", data)
    first = next(r for r in records if r["domain"] == "camera" and r["split"] == "train" and r["file"])
    crop = cv2.imread(str(output / first["file"]))
    views = preview_views(crop, spec, o["recipe"])
    tiles = []
    for name, rgb in views.items():
        tile = np.full((250, 224, 3), 30, np.uint8); tile[:224] = rgb[:, :, ::-1]
        cv2.putText(tile, name, (5, 242), cv2.FONT_HERSHEY_SIMPLEX, .38, (235, 235, 235), 1)
        tiles.append(tile)
    cv2.imwrite(str(output / "augmentation_preview.jpg"), np.concatenate(tiles, axis=1))
    print(json.dumps({"dataset": str(output), "records": len(records), "coverage": data["coverage"]}), flush=True)


def configure_model(model):
    """Adapt Classify's conv/BN affine/linear; keep all running BN state fixed."""
    model.cpu().float().eval()
    model.requires_grad_(False)
    model.model[-1].requires_grad_(True)
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def model_logits(model, x):
    output = model(x)
    if not isinstance(output, tuple) or len(output) != 2:
        raise ValueError("expected eval-mode Ultralytics classifier (probabilities, logits)")
    return output[1]


def probabilities(model, rows, dataset, spec, batch_size):
    import torch
    result = np.full((len(rows), 2), np.nan, np.float32)
    valid = [(i, r) for i, r in enumerate(rows) if r["file"]]
    with torch.inference_mode():
        for start in range(0, len(valid), batch_size):
            batch = valid[start:start + batch_size]
            x = np.concatenate([prepare_tensor(prepare_rgb(cv2.imread(str(dataset / r["file"])), spec), spec) for _, r in batch])
            result[[i for i, _ in batch]] = torch.softmax(model_logits(model, torch.from_numpy(x)), 1).numpy()
    return result


def grouped_metrics(rows, scores):
    groups = {"camera/all": [i for i,r in enumerate(rows) if r["domain"] == "camera"]}
    for distance in DISTANCES:
        groups[f"camera/{distance}"] = [i for i,r in enumerate(rows) if r["domain"] == "camera" and r["distance"] == distance]
    for source in sorted({r["source"] for r in rows if r["domain"] == "static"}):
        groups[f"static/{source}"] = [i for i,r in enumerate(rows) if r["domain"] == "static" and r["source"] == source]
    for action in sorted({r["action"] for r in rows if r["domain"] == "camera"}):
        groups[f"action/{action}"] = [i for i,r in enumerate(rows) if r["domain"] == "camera" and r["action"] == action]
    result = {}
    for name, indices in groups.items():
        if not indices:
            continue
        predictions = [CLASSES[int(scores[i].argmax())] if np.isfinite(scores[i]).all() else "UNKNOWN" for i in indices]
        measured = classification_metrics([rows[i]["label"] for i in indices], predictions, CLASSES)
        positive = [i for i in indices if rows[i]["label"] == "yawn"]
        negative = [i for i in indices if rows[i]["label"] == "no_yawn"]
        accepted = [i for i in indices if np.isfinite(scores[i]).all() and rows[i]["quality"] == "usable"]
        measured.update(unknown_quality=len(indices) - len(accepted),
            positive_samples=len(positive), negative_samples=len(negative),
            yawn_recall_at_070_including_unknown=float(sum(i in accepted and scores[i,1] >= .70 for i in positive) / max(len(positive),1)),
            false_yawn_at_070=float(sum(i in accepted and scores[i,1] >= .70 for i in negative) / max(len(negative),1)))
        measured["brier_score"] = float(np.mean([(scores[i,1] - (rows[i]["label"] == "yawn")) ** 2
            for i in indices if np.isfinite(scores[i]).all()])) if any(np.isfinite(scores[i]).all() for i in indices) else 1.
        result[name] = measured
    return result


def validation_passed(candidate, baseline, active_distances=DISTANCES, validation_mode="camera"):
    reasons = []
    camera_keys = ("camera/all",) + tuple(f"camera/{d}" for d in active_distances) if validation_mode == "camera" else ()
    for key in camera_keys:
        item = candidate.get(key, {})
        if min(item.get("positive_samples", 0), item.get("negative_samples", 0)) < 10:
            reasons.append(f"insufficient_validation:{key}")
        if item.get("macro_f1", 0) < .85 or item.get("yawn_recall_at_070_including_unknown", 0) < .85:
            reasons.append(f"recall_or_f1:{key}")
        if item.get("false_yawn_at_070", 1) > .05:
            reasons.append(f"false_yawn:{key}")
    static_keys = [k for k in baseline if k.startswith("static/")]
    if validation_mode == "static_only":
        for key in ("static/legacy", "static/smiles", "static/genki"):
            item = candidate.get(key, {})
            if item.get("negative_samples", 0) < 10 or (key == "static/legacy" and item.get("positive_samples", 0) < 10):
                reasons.append(f"insufficient_static_validation:{key}")
    for key in static_keys:
        item = candidate.get(key, {})
        if (item.get("macro_f1", 0) < baseline[key]["macro_f1"] - .02 or
                item.get("false_yawn_at_070", 1) > baseline[key]["false_yawn_at_070"] + .01 or
                (validation_mode == "static_only" and baseline[key].get("positive_samples", 0) and
                 item.get("yawn_recall_at_070_including_unknown", 0) < baseline[key]["yawn_recall_at_070_including_unknown"] - .02)):
            reasons.append(f"static_regression:{key}")
    return reasons


def selection_score(metrics, active_distances=DISTANCES, validation_mode="camera"):
    if validation_mode == "camera":
        return float(np.mean([metrics[f"camera/{d}"]["macro_f1"] for d in active_distances]))
    static = [v for k, v in metrics.items() if k.startswith("static/")]
    if not static:
        raise ValueError("no static validation for selection")
    # Confidence calibration breaks F1 ties; camera/train scores never enter selection.
    return float(np.mean([v["macro_f1"] - .05 * v["brier_score"] for v in static]))


def train(o, epochs=None):
    import torch
    from ultralytics import YOLO
    from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
    torch.set_num_threads(o["threads"]); torch.manual_seed(o["seed"])
    config = load_config(o["runtime_config"])
    data = verify_prepared_dataset(o["dataset"], config, o["recipe"])
    checked_annotations(o)  # recheck held-out registry and assignments before fitting
    if data['camera_split_mode'] != o['split_mode']:
        raise ValueError('split mode changed; prepare a new dataset')
    if (data.get('active_distances', list(DISTANCES)) != list(o['active_distances']) or
            data.get('validation_mode', 'camera') != o['validation_mode']):
        raise ValueError('distance/validation scope changed; prepare a new dataset')
    output = o["output"]
    if output.exists() and any(output.iterdir()):
        raise ValueError("candidate directory nonempty; choose a new output path in YAML")
    output.mkdir(parents=True, exist_ok=True)
    spec = data["runtime_spec"]
    loaded = YOLO(str(artifact_path(config.manifest, spec["artifacts"]["torch"])))
    if [loaded.names[i] for i in range(2)] != list(CLASSES):
        raise ValueError("checkpoint labels differ from runtime class order")
    model = loaded.model
    count = configure_model(model)
    head_prefix = f"model.{len(model.model)-1}."
    immutable_state = {k: v.detach().clone() for k, v in model.state_dict().items()
        if not k.startswith(head_prefix) or 'running_' in k or 'num_batches_tracked' in k}
    validation = [r for r in data["records"] if r["split"] == "val" and
                  (o["validation_mode"] == "camera" or r["domain"] == "static")]
    training = [r for r in data["records"] if r["split"] == "train" and r["file"] and r["train_eligible"]]
    baseline = grouped_metrics(validation, probabilities(model, validation, o["dataset"], spec, o["batch_size"]))
    class NativeDataset(Dataset):
        def __init__(self):
            self.rng = np.random.default_rng(o["seed"])
        def __len__(self):
            return len(training)
        def __getitem__(self, i):
            row = training[i]
            crop = cv2.imread(str(o["dataset"] / row["file"]))
            rgb = training_rgb(crop, spec, "train", o["recipe"], self.rng)
            return torch.from_numpy(prepare_tensor(rgb,spec)[0]), CLASSES.index(row["label"])
    # Balance classes, then distance/actions/sources; long clips cannot dominate.
    def group(row):
        return row["domain"], row["label"], row["distance"], row["action"], row["source"]
    groups = Counter(group(r) for r in training)
    group_counts = Counter((g[0],g[1]) for g in groups)
    domain_count = len({r["domain"] for r in training})
    weights = [(o["camera_weight"] if r["domain"] == "camera" else 1-o["camera_weight"]) /
        (2 * group_counts[r["domain"],r["label"]] * groups[group(r)]) if domain_count == 2 else
        1/(2 * group_counts[r["domain"],r["label"]] * groups[group(r)]) for r in training]
    sampler = WeightedRandomSampler(weights, min(len(training), o["max_epoch_samples"]), replacement=True,
        generator=torch.Generator().manual_seed(o["seed"]))
    loader = DataLoader(NativeDataset(), batch_size=o["batch_size"], sampler=sampler, num_workers=0)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
        lr=o["learning_rate"], weight_decay=o["weight_decay"])
    best, selected, trials, stale = -float("inf"), None, [], 0
    for epoch in range(1, (epochs or o["epochs"]) + 1):
        model.eval()  # gradients still flow; all BN running stats remain fixed
        loss_total = samples = 0
        for x, y in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = torch.nn.functional.cross_entropy(model_logits(model, x), y)
            loss.backward(); optimizer.step()
            loss_total += float(loss.detach()) * len(y); samples += len(y)
        candidate = grouped_metrics(validation, probabilities(model, validation, o["dataset"], spec, o["batch_size"]))
        reasons = validation_passed(candidate, baseline, o["active_distances"], o["validation_mode"])
        score = selection_score(candidate, o["active_distances"], o["validation_mode"])
        trial = {"epoch": epoch, "loss": loss_total / max(samples,1), "score": score,
                 "rejection_reasons": reasons, "validation": candidate}
        trials.append(trial)
        if not reasons and score > best:
            best, selected, stale = score, (copy.deepcopy(model.state_dict()), trial), 0
        else:
            stale += 1
        print(json.dumps({k:v for k,v in trial.items() if k != "validation"}), flush=True)
        if selected is not None and stale >= o["patience"]:
            break
    report = {"baseline_validation": baseline, "trials": trials, "trainable_parameters": count,
        "selection_split": "val", "test_used_for_selection": False,
        "selection_domain": "static_only" if o["validation_mode"] == "static_only" else "camera_and_static",
        "active_distances": list(o["active_distances"]), "validation_mode": o["validation_mode"],
        "camera_validation_pending": o["validation_mode"] == "static_only",
        "dataset_sha256": sha256(o["dataset"] / "dataset.json"), "config_sha256": sha256(o["options_path"]),
        "dataset_path": str(o["dataset"]),
        "selected": selected[1] if selected else None, "event_acceptance_measured": False}
    json_save(output / "validation.json", report)
    if selected is None:
        raise RuntimeError("No candidate passed validation. See validation.json; collect more data before deployment.")
    model.load_state_dict(selected[0]); model.eval()
    report['frozen_backbone_and_bn_buffers_unchanged'] = all(
        torch.equal(model.state_dict()[k], v) for k, v in immutable_state.items())
    if not report['frozen_backbone_and_bn_buffers_unchanged']:
        json_save(output / 'validation.json', report)
        raise RuntimeError('Frozen model state changed; no candidate exported.')
    loaded.ckpt.update(train_metrics={}, train_results={}, epoch=selected[1]["epoch"])
    pending_checkpoint = output / 'candidate_yawn.pt'
    loaded.save(pending_checkpoint)
    serialized = YOLO(str(pending_checkpoint)).model.cpu().float().eval()
    locked_validation = grouped_metrics(validation,probabilities(serialized,validation,o['dataset'],spec,o['batch_size']))
    report['serialized_validation'] = locked_validation
    report['serialized_rejection_reasons'] = validation_passed(locked_validation,baseline,
        o['active_distances'],o['validation_mode'])
    json_save(output / 'validation.json',report)
    if report['serialized_rejection_reasons']:
        raise RuntimeError('Serialized checkpoint failed validation; no runtime manifest exported.')
    pending_checkpoint.replace(output / 'best_yawn.pt')
    export_candidate(output, config, data, report)


def export_candidate(output, config, data, report):
    import torch
    import onnx
    from ultralytics import YOLO
    model = YOLO(str(output / "best_yawn.pt")).model.cpu().float().eval()
    model.model[-1].export = True
    onnx_path = output / "best_yawn.onnx"
    torch.onnx.export(model, torch.zeros(1,3,224,224), str(onnx_path), input_names=["images"],
        output_names=["probabilities"], opset_version=12, do_constant_folding=True)
    onnx.checker.check_model(onnx.load(onnx_path))
    contract = copy.deepcopy(read_manifest(config.manifest))
    for model_spec in contract["classifiers"].values():
        for artifact in model_spec["artifacts"].values():
            artifact["file"] = os.path.relpath(artifact_path(config.manifest, artifact), output).replace(os.sep,"/")
    contract["detector"]["file"] = os.path.relpath(artifact_path(config.manifest, contract["detector"]), output).replace(os.sep,"/")
    contract["classifiers"]["yawn"]["artifacts"] = {backend: {"file": f"best_yawn.{ext}",
        "sha256": sha256(output / f"best_yawn.{ext}")} for backend,ext in (("torch","pt"),("onnx","onnx"))}
    contract.setdefault("refinement", {})["yawn"] = {"method": "distance-aware Classify conv/BN affine/Linear fine-tuning",
        "baseline_sha256": data["runtime_spec"]["artifacts"]["torch"]["sha256"],
        "dataset_sha256": report["dataset_sha256"], "training_augmentation": data["augmentation"],
        "augmentation_at_inference": False, "selection_split": "val",
        "active_distances": data.get("active_distances", list(DISTANCES)),
        "validation_mode": data.get("validation_mode", "camera"),
        "camera_validation_pending": data.get("validation_mode", "camera") == "static_only",
        "camera_split_mode": data["camera_split_mode"], "runtime_config_sha256": data["runtime_config_sha256"]}
    contract["deployment_validation"] = ("Experimental near/medium candidate selected on retained static validation only; "
        "independent camera validation, events, people and Radxa pending" if data.get("validation_mode") == "static_only" else
        "Validation-selected development candidate; events, independent people and Radxa pending")
    json_save(output / "manifest.json", contract)
    # Check serialized PT/ONNX with actual validation crops, never test data.
    from driver_monitor.models import Classifier
    pt = Classifier(output / "manifest.json", "yawn", "torch")
    ort = Classifier(output / "manifest.json", "yawn", "onnx")
    deltas = []
    try:
        for row in [r for r in data["records"] if r["split"] == "val" and r["file"]][:32]:
            crop = cv2.imread(str(Path(report.get("dataset_path", ".")) / row["file"]))
            if crop is None:
                raise ValueError("parity crop unavailable")
            a, b = pt.predict(crop), ort.predict(crop)
            deltas.append(max(abs(a[c]-b[c]) for c in CLASSES))
    finally:
        pt.close(); ort.close()
    json_save(output / "parity.json", {"samples": len(deltas), "max_probability_delta": max(deltas),
        "passed": max(deltas) <= 1e-4})
    if max(deltas) > 1e-4:
        raise ValueError("export parity failed; candidate must not be deployed")
    # A full copy of the runtime settings avoids introducing new crop/quality defaults.
    runtime = asdict(config)
    runtime["manifest"] = "manifest.json"
    runtime["log_dir"] = str(config.log_dir)
    runtime["backend"] = "onnx"
    (output / "runtime.yaml").write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")
    print(f"Candidate: {output / 'manifest.json'}; run the held-out video evaluation before use.")


def evaluate(o, manifest_path, reviews):
    """Full-rate yawn channel replay; held-out bytes never enter fitting/selection."""
    from driver_monitor import Monitor, Observation
    from driver_monitor.models import Classifier
    if not reviews:
        raise ValueError("evaluate requires --review with a reviewed held-out clip JSON")
    config = load_config(o["runtime_config"], manifest=manifest_path)
    classifier = Classifier(config.manifest, "yawn", "onnx", o["threads"])
    results = []
    try:
        for path in reviews:
            labels = json.loads(path.read_text(encoding="utf-8"))
            if labels.get("training_allowed") is not False or labels.get("checkpoint_selection_allowed") is True:
                raise ValueError("use explicitly locked review files for evaluation")
            intervals = labels.get("reviewed_intervals", labels.get("intervals", []))
            intervals = [{**r,"label":"no_yawn" if r['label']=='normal' else r['label']} for r in intervals]
            if not intervals or any(r['label'] not in CLASSES for r in intervals):
                raise ValueError('held-out intervals need normal/no_yawn or yawn labels')
            video = ROOT / labels["video"]
            if sha256(video) != labels["video_sha256"]:
                raise ValueError("locked evaluation video changed")
            if labels.get('timestamps_sha256') and sha256(video.with_suffix('.timestamps.json')) != labels['timestamps_sha256']:
                raise ValueError('locked evaluation timestamps changed')
            monitor, vision = Monitor(config.monitor), Vision(config)
            capture = Capture(video)
            rows, scores, events, previous = [], [], [], 0
            try:
                while (packet := capture.read()) is not None:
                    result = vision.observe(orient_frame(packet.image, config.rotation_degrees), packet.timestamp)
                    prediction = classifier.predict(result.crops[2]) if result.crops and result.quality == "usable" else None
                    decision = monitor.update(Observation(packet.timestamp, yawn=prediction, quality=result.quality,
                                                          track_changed=result.track_changed))
                    if result.track_changed: previous = 0
                    if decision.yawn_count > previous: events.append(packet.timestamp)
                    previous = decision.yawn_count
                    interval = next((r for r in intervals if r["start"] <= packet.timestamp < r["end"]), None)
                    if interval:
                        rows.append({"domain":"camera", "source": video.name, "distance":"unspecified",
                            "label":interval["label"], "action":interval.get("action", interval["label"]), "quality":result.quality})
                        scores.append([prediction[c] for c in CLASSES] if prediction else [float("nan")]*2)
            finally:
                capture.close()
            measured_intervals = [{**r, "confirmations": [t for t in events if r["start"] <= t < r["end"]]} for r in intervals]
            results.append({"video_sha256":labels["video_sha256"], "review_sha256":sha256(path),
                "classification":grouped_metrics(rows,np.asarray(scores)), "yawn_channel_confirmations":events,
                "reviewed_intervals":measured_intervals, "events_outside_reviewed_intervals":[t for t in events if not any(
                    r["start"] <= t < r["end"] for r in intervals)],
                "limitation":"same-person staged yawns; short intervals may be < confirmation duration; eye/alert channel not measured"})
    finally:
        classifier.close()
    json_save(o["output"] / "heldout_evaluation.json", {"manifest_sha256":sha256(manifest_path),
        "test_used_for_selection":False, "videos":results})
    print(f"Held-out evaluation: {o['output'] / 'heldout_evaluation.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("init", "check", "prepare", "train", "evaluate"))
    parser.add_argument("--config", type=Path, default=ROOT / "configs/yawn_distance_training.yaml")
    parser.add_argument("--epochs", type=int, help="optional short pipeline check; never reports acceptance")
    parser.add_argument("--manifest", type=Path, help="locked candidate manifest for evaluate")
    parser.add_argument("--review", type=Path, action="append", default=[], help="held-out video review JSON; may repeat")
    args = parser.parse_args()
    if args.epochs is not None and args.epochs < 1:
        parser.error("epochs must be positive")
    try:
        o = options(args.config)
        if args.stage == "init": init(o)
        elif args.stage == "check": print(json.dumps({"coverage": summarize(checked_annotations(o))}))
        elif args.stage == "prepare": prepare(o)
        elif args.stage == "train": train(o, args.epochs)
        else:
            if args.manifest is None: parser.error("evaluate requires --manifest")
            evaluate(o, args.manifest.resolve(), [p.resolve() for p in args.review])
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
