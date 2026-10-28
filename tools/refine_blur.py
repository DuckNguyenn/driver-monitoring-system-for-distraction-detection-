"""Reproducible CPU refinement on clear, real-blurred and synthetic-blurred crops.

Prepare native runtime ROIs, cache frozen features, train the linear classifier
heads, select on validation, lock/export, calibrate real validation quality,
then report held development tests. Never rewrites the active PC profile.
"""
import argparse
import copy
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for key, name in (("YOLO_CONFIG_DIR", "ultralytics"), ("MPLCONFIGDIR", "matplotlib")):
    directory = ROOT / ".cache" / name
    directory.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault(key, str(directory))

import cv2
import numpy as np
import torch
import yaml
from ultralytics import YOLO

from driver_monitor.blur import (STRESS_BLURS, apply_blur, calibrate_quality,
                                 exclude_split_duplicates, gate_metrics, training_blurs)
from driver_monitor.capture import Capture
from driver_monitor.config import load_config
from driver_monitor.evaluation import classification_metrics
from driver_monitor.exporting import export_models
from driver_monitor.models import Classifier, artifact_path, prepare_rgb, prepare_tensor, read_manifest, sha256
from driver_monitor.vision import Vision, orient_frame, quality_metrics
from refine_eye_head import augment as eye_augment


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def settings(path):
    path = Path(path).resolve()
    values = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("baseline_config", "cache", "output", "eye_records", "yawn_records",
                "camera_labels", "camera_eye_labels", "real_eye_labels"):
        if values.get(key):
            values[key] = (path.parent / values[key]).resolve()
    values["settings_path"] = path
    if values["epochs"] < 20 or values["batch_size"] < 1:
        raise ValueError("epochs >=20 and batch_size >=1 required")
    torch.set_num_threads(values["threads"])
    torch.manual_seed(values["seed"])
    np.random.seed(values["seed"])
    cv2.setNumThreads(1)
    return values


def interval_for(timestamp, intervals):
    matches = [r for r in intervals if r["start"] <= timestamp < r["end"]]
    if len(matches) > 1:
        raise ValueError("overlapping camera labels")
    return matches[0] if matches else None


def reviewed_eye_rows(path):
    reviewed = json.loads(path.read_text(encoding="utf-8"))
    if reviewed.get("video") and sha256(ROOT / reviewed["video"]) != reviewed["video_sha256"]:
        raise ValueError("reviewed camera video changed")
    for frame in reviewed["records"]:
        for eye, label in enumerate(frame["eye_labels"]):
            if label == "Unknown":
                continue
            if label not in ("Open", "Closed"):
                raise ValueError("invalid reviewed eye label")
            yield {**frame, "eye_index": eye, "label": label, "source": "roi",
                   "dataset": frame.get("dataset", "camera_eye"), "variant": "base"}


def static_parents(kind, options, config, extra_only=False):
    """Retain existing assignments and recover the identical original-pixel ROI."""
    path = options[f"{kind}_records"]
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["records"]
    if kind == "eye":
        rows = [] if extra_only else [r for r in rows if r["variant"] == "base"]
        if not extra_only and options.get("camera_eye_labels"):
            rows.extend(reviewed_eye_rows(options["camera_eye_labels"]))
        if options.get("real_eye_labels"):
            rows.extend(reviewed_eye_rows(options["real_eye_labels"]))
    current, image, result = None, None, None
    vision = Vision(config)
    for old in rows:
        if old["path"] != current:
            current = old["path"]
            source = ROOT / current
            if sha256(source) != old["sha256"]:
                raise ValueError(f"source image changed: {current}")
            image = cv2.imread(str(source))
            if image is None:
                raise ValueError(f"unreadable source: {current}")
            vision.previous_box = None
            vision.eye_motion.reset()
            result = vision.observe(image)
        crop = image
        runtime_crop = False
        if kind == "eye":
            view = "eye" if old["source"] == "roi" else "legacy"
            if old["source"] == "roi":
                if result.crops is None:
                    raise ValueError(f"reviewed ROI lost face geometry: {current}")
                if old.get("eye_boxes") and list(map(list, result.boxes[:2])) != old["eye_boxes"]:
                    raise ValueError(f"reviewed eye boxes changed: {current}")
                crop = result.crops[old["eye_index"]]
                runtime_crop = True
            group = "legacy" if old["source"] == "legacy" else old.get("dataset", "manual")
        else:
            view = old["variant"]
            if view == "face":
                if result.crops is None or result.quality not in ("usable", "blurry"):
                    continue
                crop, runtime_crop = result.crops[2], True
            elif view == "gray_train":
                base = result.crops[2] if old["quality"] == "usable" else image
                crop = cv2.cvtColor(cv2.cvtColor(base, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
            elif old["source"] == "genki" and result.crops is not None:
                crop, runtime_crop = result.crops[2], True
            group = f"legacy_{view}" if old["source"] == "legacy" else old["source"]
        # A gray train view stays an augmentation, never a real validation row.
        variant = "gray_train" if view == "gray_train" else "base"
        parent_id = f"{current}:{old.get('eye_index', -1)}:{view}"
        row = {**old, "parent_id": parent_id, "group": group, "view": view,
               "kind": kind, "variant": variant, "origin": "real" if variant == "base" else "synthetic_other",
               "runtime_crop": runtime_crop, "quality": result.quality if runtime_crop else "pre_cropped",
               "metrics": result.metrics if runtime_crop else None,
               "geometry_valid": runtime_crop, "expected_input_sha256": old.get("input_sha256")}
        row.pop("feature", None)
        # Keep previously trained fallbacks, but do not manufacture quality
        # metrics for a pre-cropped eye or a 64px smile image.
        yield crop, row


def camera_parents(options, config):
    labels_path = options["camera_labels"]
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    capture = Capture(ROOT / labels["video"], config.width, config.height)
    vision, last = Vision(config), {}
    try:
        while (packet := capture.read()) is not None:
            result = vision.observe(orient_frame(packet.image, config.rotation_degrees), packet.timestamp)
            interval = interval_for(packet.timestamp, labels["intervals"])
            if interval is None or result.crops is None or result.quality not in ("usable", "blurry"):
                continue
            # Use 5 Hz training and validation samples, not 30 correlated
            # samples per second. Real blur is included; dark/invalid faces are not.
            key = (interval["split"], interval["action"])
            if packet.timestamp - last.get(key, -float("inf")) < .20:
                continue
            last[key] = packet.timestamp
            crop = result.crops[2]
            row = {"kind": "yawn", "path": labels["video"], "frame": packet.index,
                   "timestamp": packet.timestamp, "split": interval["split"], "label": interval["label"],
                   "source": "camera", "group": f"camera_{interval['action']}", "view": "face",
                   "variant": "base", "origin": "real", "runtime_crop": True,
                   "geometry_valid": True, "quality": result.quality, "metrics": result.metrics,
                   "sha256": hashlib.sha256(packet.image.tobytes()).hexdigest(),
                   "parent_id": f"{labels['video']}:{packet.index}:face"}
            yield crop, row
    finally:
        capture.close()


class FeatureWriter:
    def __init__(self, kind, options, config):
        self.kind, self.options = kind, options
        self.classifier = Classifier(config.manifest, kind, "torch", options["threads"])
        self.spec = self.classifier.spec
        self.records, self.vectors, self.pending, self.pending_rows, self.caught = [], [], [], [], []
        self.hook = self.classifier.model.model[-1].linear.register_forward_pre_hook(
            lambda module, args: self.caught.append(args[0].detach().numpy().copy()))
        self.parity_counts = Counter()
        self.directory = options["cache"] / kind
        (self.directory / "parity").mkdir(parents=True, exist_ok=True)

    def add(self, image, row):
        rgb = prepare_rgb(image, self.spec)
        digest = hashlib.sha256(rgb.tobytes()).hexdigest()
        if row.get("expected_input_sha256") and digest != row["expected_input_sha256"]:
            raise ValueError(f"crop/preprocessing changed: {row['parent_id']}")
        row = {**row, "input_sha256": digest, "crop_sharpness": quality_metrics(image)["sharpness"]}
        row.pop("expected_input_sha256", None)
        # A compact pixel sample verifies serialized PT/ONNX parity later.
        key = (row["split"], row["group"], row["variant"], row["label"])
        if row["split"] != "train" and self.parity_counts[key] < 1:
            file = f"parity/{len(self.vectors) + len(self.pending):06d}.png"
            if not cv2.imwrite(str(self.directory / file), rgb[:, :, ::-1]):
                raise RuntimeError("cannot save parity pixels")
            row["parity_file"] = file
            self.parity_counts[key] += 1
        self.pending.append(prepare_tensor(rgb, self.spec))
        self.pending_rows.append(row)
        if len(self.pending) >= self.options["batch_size"]:
            self.flush()

    def flush(self):
        if not self.pending:
            return
        self.caught.clear()
        with torch.inference_mode():
            self.classifier.model(torch.from_numpy(np.concatenate(self.pending)))
        for row, vector in zip(self.pending_rows, self.caught[0]):
            self.records.append({**row, "feature": len(self.vectors)})
            self.vectors.append(vector)
        self.pending.clear()
        self.pending_rows.clear()

    def parent(self, image, row):
        self.add(image, row)
        if row["variant"] != "base":
            return
        if row["split"] == "train":
            if self.kind == "eye":
                for name, other in eye_augment(image):
                    if name != "base":
                        self.add(other, {**row, "variant": name, "origin": "synthetic_other",
                                         "metrics": None, "expected_input_sha256": None})
            # Train both classes with Gaussian + motion, before live RGB/resize.
            # Full-face legacy, eye precrops, and real camera runtime ROIs all
            # retain their source/view provenance instead of pretending to
            # be newly captured blurry frames.
            for params in training_blurs(row["split"], row["parent_id"], self.options["seed"]):
                self.add(apply_blur(image, params), {**row, "variant": params["kind"],
                    "origin": "synthetic_blur", "blur": params, "metrics": None,
                    "expected_input_sha256": None})
        else:
            for params in STRESS_BLURS:
                self.add(apply_blur(image, params), {**row, "variant": params["kind"],
                    "origin": "synthetic_stress", "blur": params, "metrics": None,
                    "expected_input_sha256": None})

    def finish(self, config):
        self.flush()
        self.hook.remove()
        kept, excluded = exclude_split_duplicates(self.records)
        matrix = np.stack(self.vectors).astype(np.float32)
        np.savez_compressed(self.directory / "features.npz", features=matrix)
        counts = Counter(f"{r['split']}/{r['group']}/{r['variant']}/{r['label']}" for r in kept)
        input_paths = [self.options[f"{self.kind}_records"], self.options["camera_labels"]]
        if self.kind == "eye" and self.options.get("camera_eye_labels"):
            input_paths.append(self.options["camera_eye_labels"])
        if self.kind == "eye" and self.options.get("real_eye_labels"):
            input_paths.append(self.options["real_eye_labels"])
            source_metadata = json.loads(self.options["real_eye_labels"].read_text(encoding="utf-8"))
            source_name = source_metadata.get("source_manifest")
            if not source_name and source_metadata.get("source_sha256") and all(
                    r.get("dataset", "").startswith("cew") for r in source_metadata["records"]):
                source_name = ".cache/cew/source.json"
            if source_name:
                source_manifest = ROOT / source_name
                if sha256(source_manifest) != source_metadata["source_sha256"]:
                    raise ValueError("reviewed real blur source metadata changed")
                input_paths.append(source_manifest)
        sources = {str(p.relative_to(ROOT)): sha256(p) for p in input_paths}
        labels = json.loads(self.options["camera_labels"].read_text(encoding="utf-8"))
        video = ROOT / labels["video"]
        sources[str(video.relative_to(ROOT))] = sha256(video)
        sidecar = video.with_suffix(".timestamps.json")
        if sidecar.is_file():
            sources[str(sidecar.relative_to(ROOT))] = sha256(sidecar)
        data = {"schema_version": 1, "kind": self.kind, "records": kept,
                "feature_count": len(matrix), "features_sha256": sha256(self.directory / "features.npz"),
                "baseline_config": str(self.options["baseline_config"].relative_to(ROOT)),
                "config_sha256": config.fingerprint(), "manifest_sha256": sha256(config.manifest),
                "settings_sha256": sha256(self.options["settings_path"]), "sources": sources,
                "augmentation_seed": self.options["seed"], "augmentation_protocol_version": 1,
                "excluded_cross_split_parents": excluded, "counts": dict(counts),
                "subject_independence": "NOT established; retained historical development splits and one previously used camera clip",
                "method": "native runtime ROIs; blur before prepare_rgb; freeze extractor and refine final linear head"}
        save(self.directory / "records.json", data)
        print(json.dumps({"prepared": self.kind, "feature_count": len(matrix), "retained": len(kept),
              "excluded_cross_split_parents": len(excluded),
              "real_blurry_training": dict(Counter(r['label'] for r in kept if r['split'] == 'train'
                  and r['variant'] == 'base' and r['quality'] == 'blurry'))}), flush=True)
        self.classifier.close()


def prepare(options, kinds):
    config = load_config(options["baseline_config"])
    for kind in kinds:
        writer = FeatureWriter(kind, options, config)
        for index, (image, row) in enumerate(static_parents(kind, options, config)):
            writer.parent(image, row)
            if index and index % 500 == 0:
                print(f"{kind}: {index} source crops / {len(writer.records)} features", flush=True)
        if kind == "yawn":
            for image, row in camera_parents(options, config):
                writer.parent(image, row)
        writer.finish(config)


def load_cache(options, kind):
    directory = options["cache"] / kind
    data = json.loads((directory / "records.json").read_text(encoding="utf-8"))
    config = load_config(options["baseline_config"])
    if (data["features_sha256"] != sha256(directory / "features.npz")
            or data["config_sha256"] != config.fingerprint()
            or data["manifest_sha256"] != sha256(config.manifest)):
        raise ValueError("stale features/config; prepare again")
    # Learning rates, epochs and the gate grid do not change the feature
    # pixels. Seed changes do, and must trigger fresh preparation.
    if data.get("augmentation_seed", options["seed"]) != options["seed"]:
        raise ValueError("augmentation seed changed; prepare again")
    for row in data["records"]:
        if row["origin"] == "synthetic_blur" and row["blur"] not in training_blurs(
                row["split"], row["parent_id"], options["seed"]):
            raise ValueError("cached augmentation differs from current protocol/seed")
    for path, digest in data["sources"].items():
        if sha256(ROOT / path) != digest:
            raise ValueError(f"label/source provenance changed: {path}")
    features = torch.from_numpy(np.load(directory / "features.npz")["features"])
    return data, features, config


def extend_eye(options):
    """Append reviewed real blur to a verified cache without recomputing siblings."""
    if not options.get("real_eye_labels"):
        raise ValueError("real_eye_labels required")
    data, features, config = load_cache(options, "eye")
    writer = FeatureWriter("eye", options, config)
    writer.records.extend(data["records"])
    writer.vectors.extend(features.numpy())
    known = {r["parent_id"] for r in writer.records}
    for image, row in static_parents("eye", options, config, extra_only=True):
        if row["parent_id"] not in known:
            writer.parent(image, row)
    writer.finish(config)


def probabilities(head, features):
    with torch.inference_mode():
        return torch.softmax(head(features), 1).numpy()


def extractor_digest(model):
    linear = model.model[-1].linear
    prefix = next(name for name, module in model.named_modules() if module is linear) + "."
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        if not name.startswith(prefix):
            digest.update(name.encode())
            digest.update(value.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def group_metrics(rows, p, classes):
    result = classification_metrics([r["label"] for r in rows],
        [classes[int(p[r["feature"]].argmax())] for r in rows], classes)
    result["confidence"] = {}
    for index, label in enumerate(classes):
        threshold = .8 if "Closed" in classes else (.7 if label == "yawn" else .65)
        chosen = [r for r in rows if r["label"] == label]
        result["confidence"][label] = {"samples": len(chosen),
            "recall": sum(p[r["feature"], index] >= threshold for r in chosen) / max(len(chosen), 1),
            "false_confident": int(sum(p[r["feature"], index] >= threshold for r in rows if r["label"] != label))}
    return result


def metrics(rows, p, classes, split):
    rows = [r for r in rows if r["split"] == split]
    groups = {"all": rows}
    for variant in ("base", "gaussian", "motion"):
        groups[variant] = [r for r in rows if r["variant"] == variant]
    for group in sorted({r["group"] for r in rows}):
        groups[f"base/{group}"] = [r for r in rows if r["group"] == group and r["variant"] == "base"]
    return {name: group_metrics(chosen, p, classes) for name, chosen in groups.items() if chosen}


def validation_guard(baseline, candidate):
    reasons = []
    for group, b in baseline.items():
        c = candidate[group]
        if c["macro_f1"] + 1e-12 < b["macro_f1"] - .02:
            reasons.append(f"f1_regression:{group}")
        for label, before in b["confidence"].items():
            after = c["confidence"][label]
            if before["samples"] and after["recall"] + 1e-12 < before["recall"] - .02:
                reasons.append(f"recall_regression:{group}/{label}")
            if after["false_confident"] > before["false_confident"]:
                reasons.append(f"false_confident_increase:{group}/{label}")
    return reasons


def live_validation_guard(rows, baseline_p, candidate_p, config, classes):
    """Preserve confident decisions on previously usable real validation ROIs."""
    real = [r for r in rows if r["split"] == "val" and r["variant"] == "base" and r["runtime_crop"]]
    groups = {"all": real}
    for name in sorted({r["group"] for r in real}):
        groups[name] = [r for r in real if r["group"] == name]
    positive = "Closed" if "Closed" in classes else "yawn"
    reasons = []
    for name, subset in groups.items():
        b = gate_metrics(subset, baseline_p, config, classes, positive)
        c = gate_metrics(subset, candidate_p, config, classes, positive)
        for label, after in c["classes"].items():
            before = b["classes"][label]
            if after["recall_including_unknown"] + 1e-12 < before["recall_including_unknown"]:
                reasons.append(f"live_recall_regression:{name}/{label}")
            if after["false_confident"] > before["false_confident"]:
                reasons.append(f"live_false_confident_increase:{name}/{label}")
    return reasons


def train(options, kinds):
    options["output"].mkdir(parents=True, exist_ok=True)
    for kind in kinds:
        data, features, config = load_cache(options, kind)
        if kind == "eye" and options.get("real_eye_labels") and str(options["real_eye_labels"].relative_to(ROOT)) not in data["sources"]:
            raise ValueError("new real eye labels have not been prepared; run extend-eye or prepare")
        spec = read_manifest(config.manifest)["classifiers"][kind]
        classes = spec["classes"]
        loaded = YOLO(str(artifact_path(config.manifest, spec["artifacts"]["torch"])))
        loaded.model.cpu().float().eval()
        initial = copy.deepcopy(loaded.model.model[-1].linear).requires_grad_(False)
        rows = data["records"]
        baseline_p = probabilities(initial, features)
        baseline_val = metrics(rows, baseline_p, classes, "val")
        training = [r for r in rows if r["split"] == "train"]
        categories = {"real": .55, "synthetic_other": .15, "synthetic_blur": .30}
        counts = Counter((r["group"], r["label"], r["origin"]) for r in training)
        weights = torch.tensor([categories[r["origin"]] / counts[r["group"], r["label"], r["origin"]]
                                for r in training])
        weights /= weights.sum()
        x = features[[r["feature"] for r in training]]
        y = torch.tensor([classes.index(r["label"]) for r in training])
        method = options.get(kind, {})
        anchor_weight = float(method.get("clear_anchor_weight", 0))
        if not 0 <= anchor_weight < 1:
            raise ValueError("clear_anchor_weight must be in [0,1)")
        clear_indexes = [i for i,r in enumerate(training) if r["origin"] != "synthetic_blur"]
        anchor_x = x[clear_indexes]
        anchor_weights = weights[clear_indexes]
        anchor_weights /= anchor_weights.sum()
        with torch.no_grad():
            teacher = torch.softmax(initial(anchor_x), 1)
        trials, selected, best = [], None, -float("inf")
        for lr in method.get("learning_rates", options["learning_rates"]):
            for regularization in method.get("regularization", options["regularization"]):
                head = copy.deepcopy(initial).requires_grad_(True)
                optimizer = torch.optim.Adam(head.parameters(), lr=lr)
                for epoch in range(1, options["epochs"] + 1):
                    optimizer.zero_grad(set_to_none=True)
                    cross_entropy = (torch.nn.functional.cross_entropy(head(x), y, reduction="none") * weights).sum()
                    penalty = sum((p - q).square().sum() for p, q in zip(head.parameters(), initial.parameters()))
                    anchor = (torch.nn.functional.kl_div(torch.log_softmax(head(anchor_x),1), teacher,
                              reduction="none").sum(1) * anchor_weights).sum()
                    loss = (1-anchor_weight)*cross_entropy + anchor_weight*anchor + regularization * penalty
                    loss.backward()
                    optimizer.step()
                    if epoch % 20 and epoch != options["epochs"]:
                        continue
                    p = probabilities(head, features)
                    val = metrics(rows, p, classes, "val")
                    rejection = validation_guard(baseline_val, val)
                    rejection += live_validation_guard(rows, baseline_p, p, config, classes)
                    score = np.mean([m["macro_f1"] + np.mean([c["recall"] for c in m["confidence"].values()
                                      if c["samples"]]) for m in val.values()])
                    trial = {"learning_rate": lr, "regularization": regularization, "epoch": epoch,
                             "clear_anchor_weight": anchor_weight,
                             "score": float(score), "passed": not rejection, "rejection_reasons": rejection,
                             "validation": val}
                    trials.append(trial)
                    print(json.dumps({"kind": kind, **{k:v for k,v in trial.items() if k != "validation"}}), flush=True)
                    if not rejection and score > best:
                        best, selected = score, (copy.deepcopy(head.state_dict()), trial)
        report = {"kind": kind, "baseline_validation": baseline_val, "trials": trials,
                  "selected": selected[1] if selected else None,
                  "train_counts": dict(Counter(f"{r['group']}/{r['origin']}/{r['label']}" for r in training)),
                  "feature_provenance_sha256": sha256(options["cache"] / kind / "records.json"),
                  "settings_sha256": sha256(options["settings_path"]),
                  "independent_camera_acceptance": False}
        save(options["output"] / f"{kind}.training.json", report)
        if selected is None:
            raise RuntimeError(f"No {kind} candidate passed validation; active model/configuration unchanged")
        loaded.model.model[-1].linear.load_state_dict(selected[0])
        loaded.ckpt["train_metrics"], loaded.ckpt["train_results"] = {}, {}
        loaded.ckpt["epoch"] = selected[1]["epoch"]
        loaded.ckpt["refinement"] = {"method": data["method"], "baseline_sha256": spec["artifacts"]["torch"]["sha256"],
            "feature_provenance_sha256": report["feature_provenance_sha256"], "seed": options["seed"],
            "selected_split": "val", "subject_independence": data["subject_independence"]}
        checkpoint = options["output"] / f"best_{kind}.pt"
        loaded.save(checkpoint)
        serialized = YOLO(str(checkpoint)).model.cpu().float().eval()
        if extractor_digest(serialized) != extractor_digest(loaded.model):
            raise RuntimeError("serialized frozen extractor changed")
        locked_val = metrics(rows, probabilities(serialized.model[-1].linear, features), classes, "val")
        locked_rejection = validation_guard(baseline_val, locked_val)
        locked_rejection += live_validation_guard(rows, baseline_p,
            probabilities(serialized.model[-1].linear, features), config, classes)
        report["locked_validation"] = locked_val
        report["locked_validation_rejection"] = locked_rejection
        report["frozen_extractor_sha256"] = extractor_digest(serialized)
        report["checkpoint_sha256"] = sha256(checkpoint)
        save(options["output"] / f"{kind}.training.json", report)
        if locked_rejection:
            raise RuntimeError(f"serialized {kind} checkpoint failed validation; active model unchanged")
        print(f"Locked {kind} checkpoint", flush=True)


def export(options):
    config = load_config(options["baseline_config"])
    detector = read_manifest(config.manifest)["detector"]
    detector = {**detector, "file": os.path.relpath(artifact_path(config.manifest, detector), options["output"]).replace(os.sep, "/")}
    save(options["output"] / "yunet.source.json", detector)
    target = export_models(options["output"], options["output"] / "best_eye.pt", options["output"] / "best_yawn.pt")
    manifest = read_manifest(target)
    manifest["refinement"] = {"eye": "eye.training.json", "yawn": "yawn.training.json"}
    manifest["deployment_validation"] = "Blur development candidate; independent cabin study and RK3576 hardware pending"
    save(target, manifest)


def locked_probabilities(options, kind, features, config):
    baseline = Classifier(config.manifest, kind, "torch", options["threads"])
    candidate = Classifier(options["output"] / "manifest.json", kind, "torch", options["threads"])
    if extractor_digest(baseline.model) != extractor_digest(candidate.model):
        raise ValueError("locked candidate extractor differs from the cached feature basis")
    return (probabilities(baseline.model.model[-1].linear, features),
            probabilities(candidate.model.model[-1].linear, features))


def calibrate(options):
    rows, before, after = {}, {}, {}
    for kind in ("eye", "yawn"):
        data, features, config = load_cache(options, kind)
        before[kind], after[kind] = locked_probabilities(options, kind, features, config)
        rows[kind] = [r for r in data["records"] if r["split"] == "val" and r["variant"] == "base" and r["runtime_crop"]]
    report = calibrate_quality(rows, before, after, config, options["face_grid"], options["eye_grid"])
    report["manifest_sha256"] = sha256(options["output"] / "manifest.json")
    save(options["output"] / "quality_calibration.json", report)
    selected = report["selected"]
    if selected is None:
        raise RuntimeError("No quality threshold passed validation; active config unchanged")
    values = yaml.safe_load(options["baseline_config"].read_text(encoding="utf-8"))
    candidate_path = ROOT / "configs/camera_blur_candidate.yaml"
    values["manifest"] = os.path.relpath(options["output"] / "manifest.json", candidate_path.parent).replace(os.sep, "/")
    values["min_sharpness"] = selected["min_sharpness"]
    values["min_eye_sharpness"] = selected["min_eye_sharpness"]
    candidate_path.write_text("# Development candidate; independent blurred-camera test still pending.\n" +
                              yaml.safe_dump(values, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(json.dumps({"candidate_profile": str(candidate_path), "face_threshold": selected["min_sharpness"],
                     "eye_threshold": selected["min_eye_sharpness"],
                     "additional_validation_samples": selected["additional_accepted_validation_samples"]}), flush=True)


def evaluate(options):
    target = options["output"] / "manifest.json"
    report = {"manifest_sha256": sha256(target), "independent_camera_acceptance": False,
              "active_profile_changed": False, "classifiers": {}}
    for kind in ("eye", "yawn"):
        data, features, config = load_cache(options, kind)
        before, after = locked_probabilities(options, kind, features, config)
        classes = read_manifest(target)["classifiers"][kind]["classes"]
        candidate = Classifier(target, kind, "torch", options["threads"])
        onnx = Classifier(target, kind, "onnx", options["threads"])
        max_difference, agreement, comparisons = 0., 0, 0
        for row in data["records"]:
            if not row.get("parity_file"):
                continue
            image = cv2.imread(str(options["cache"] / kind / row["parity_file"]))
            # Saved pixels are already the exact 224x224 preprocessed input.
            pytorch, exported = candidate.predict(image), onnx.predict(image)
            max_difference = max(max_difference, max(abs(pytorch[c] - exported[c]) for c in classes))
            agreement += max(pytorch, key=pytorch.get) == max(exported, key=exported.get)
            comparisons += 1
        if comparisons == 0 or agreement != comparisons or max_difference > 1e-5:
            raise RuntimeError(f"{kind} PT/ONNX parity failed")
        result = {"baseline": {s:metrics(data["records"], before, classes, s) for s in ("val", "test", "regression")},
                  "candidate": {s:metrics(data["records"], after, classes, s) for s in ("val", "test", "regression")},
                  "parity": {"samples": comparisons, "labels_equal": agreement,
                             "max_probability_difference": max_difference, "passed": True},
                  "counts": data["counts"], "excluded_cross_split_parents": data["excluded_cross_split_parents"]}
        candidate_config_path = ROOT / "configs/camera_blur_candidate.yaml"
        if candidate_config_path.is_file():
            candidate_config = load_config(candidate_config_path)
            if candidate_config.manifest != target.resolve():
                raise ValueError("candidate profile points to another model")
            real_test = [r for r in data["records"] if r["split"] == "test" and r["variant"] == "base" and r["runtime_crop"]]
            positive = "Closed" if kind == "eye" else "yawn"
            groups = {"all": real_test}
            groups.update({name:[r for r in real_test if r["group"] == name] for name in sorted({r["group"] for r in real_test})})
            result["locked_test_quality_gates"] = {name:{
                "baseline": gate_metrics(subset,before,config,classes,positive),
                "candidate": gate_metrics(subset,after,candidate_config,classes,positive)
            } for name, subset in groups.items()}
        report["classifiers"][kind] = result
        candidate.close()
        onnx.close()
    rejections = []
    for kind, result in report["classifiers"].items():
        for name, measured in result.get("locked_test_quality_gates", {}).items():
            for label, after in measured["candidate"]["classes"].items():
                before = measured["baseline"]["classes"][label]
                if after["false_confident"] > before["false_confident"]:
                    rejections.append(f"test_false_confident_increase:{kind}/{name}/{label}")
                if after["recall_including_unknown"] + 1e-12 < before["recall_including_unknown"]:
                    rejections.append(f"test_recall_regression:{kind}/{name}/{label}")
    report["locked_development_checks_passed"] = not rejections
    report["locked_development_rejections"] = rejections
    save(options["output"] / "evaluation.json", report)
    print(f"Held development evaluation: {options['output'] / 'evaluation.json'}", flush=True)
    if rejections:
        raise RuntimeError("locked development test guard failed; gather new train/validation data before promotion")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "extend-eye", "train", "export", "calibrate", "evaluate", "all"))
    parser.add_argument("--settings", type=Path, default=ROOT / "configs/blur_training.yaml")
    parser.add_argument("--kind", choices=("eye", "yawn", "both"), default="both")
    args = parser.parse_args()
    options = settings(args.settings)
    kinds = ("eye", "yawn") if args.kind == "both" else (args.kind,)
    for stage in (("prepare", "train", "export", "calibrate", "evaluate") if args.stage == "all" else (args.stage,)):
        if stage in ("prepare", "train"):
            globals()[stage](options, kinds)
        elif stage == "extend-eye":
            extend_eye(options)
        else:
            globals()[stage](options)


if __name__ == "__main__":
    main()
