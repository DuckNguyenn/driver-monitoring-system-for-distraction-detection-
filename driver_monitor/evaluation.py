"""Measured classification, backend parity and annotated video-event metrics."""
import csv
import json
from pathlib import Path
import time
import cv2
import numpy as np

from .models import Classifier, read_manifest, sha256


def save_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"Report: {path}", flush=True)


def classification_metrics(truth, predicted, classes):
    matrix = [[0 for _ in classes] for _ in classes]
    unknown = 0
    for actual, guess in zip(truth, predicted):
        if guess not in classes:
            unknown += 1
        else:
            matrix[classes.index(actual)][classes.index(guess)] += 1
    scores = {}
    for i, label in enumerate(classes):
        tp = matrix[i][i]
        fp = sum(row[i] for row in matrix) - tp
        support = truth.count(label)
        fn = support - tp  # rejected crops are misses, not silently removed
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
        scores[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    return {"classes": classes, "confusion_matrix": matrix, "per_class": scores,
            "macro_f1": sum(s["f1"] for s in scores.values()) / len(classes),
            "accuracy": sum(matrix[i][i] for i in range(len(classes))) / max(len(truth), 1),
            "samples": len(truth), "unknown_samples": unknown, "coverage": 1 - unknown / max(len(truth), 1)}


def image_samples(root, split):
    import yaml
    root = Path(root).resolve()
    if (root / "data.yaml").is_file():
        mapping = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))["names"]
        images = root / "images" / split
        for path in sorted(images.iterdir()):
            if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                continue
            rows = (root / "labels" / split / f"{path.stem}.txt").read_text().splitlines()
            if len(rows) != 1:
                raise ValueError(f"classification requires one label: {path}")
            fields = rows[0].split()
            if len(fields) != 5 or not np.allclose(list(map(float, fields[1:])), [.5, .5, 1, 1]):
                raise ValueError("this evaluator accepts only full-frame classification labels")
            yield path, mapping[int(fields[0])]
    else:
        for directory in sorted((root / split).iterdir()):
            if directory.is_dir():
                for path in sorted(directory.iterdir()):
                    if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                        yield path, directory.name


def evaluate_classifier(config, args, compare=False):
    classes = read_manifest(config.manifest)["classifiers"][args.name]["classes"]
    model = Classifier(config.manifest, args.name, args.backend, config.cpu_threads)
    baseline = None
    reference_backend = getattr(args, "reference", "torch")
    vision = None
    truth, predicted, reference, times, errors = [], [], [], [], []
    max_error, agreement = 0.0, 0
    entries = []
    try:
        if compare:
            baseline = Classifier(config.manifest, args.name, reference_backend, config.cpu_threads)
        if args.crop == "face":
            if args.name != "yawn":
                raise ValueError("face crop evaluation is for yawn; eye data already contains eye crops")
            from .vision import Vision, orient_frame
            vision = Vision(config)
        for path, label in image_samples(args.data, args.split):
            if args.limit and len(truth) >= args.limit:
                break
            label = next((c for c in classes if c.casefold() == label.casefold()), None)
            if label is None:
                raise ValueError(f"dataset label does not exist in classifier: {path}")
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f"unreadable image: {path}")
            reason = None
            if vision:
                result = vision.observe(orient_frame(image, config.rotation_degrees))
                if result.quality == "usable":
                    image = result.crops[2]
                else:
                    reason = result.quality
            truth.append(label)
            if reason:
                predicted.append("UNKNOWN")
                if baseline:
                    reference.append("UNKNOWN")
                entries.append({"file": str(path), "truth": label, "prediction": "UNKNOWN", "reason": reason})
                continue
            start = time.perf_counter()
            values = model.predict(image)
            times.append((time.perf_counter() - start) * 1000)
            guess = max(values, key=values.get)
            predicted.append(guess)
            entries.append({"file": str(path), "truth": label, "prediction": guess, "probabilities": values})
            if baseline:
                expected = baseline.predict(image)
                ref = max(expected, key=expected.get)
                reference.append(ref)
                agreement += guess == ref
                max_error = max(max_error, max(abs(values[c] - expected[c]) for c in classes))
    finally:
        model.close()
        if baseline:
            baseline.close()
    if not truth:
        raise ValueError("dataset contains no samples")
    metrics = classification_metrics(truth, predicted, classes)
    report = {"type": "static_image_classification", "classifier": args.name, "backend": args.backend,
              "split": args.split, "crop": args.crop, "config_sha256": config.fingerprint(),
              "metrics": metrics, "inference_p95_ms": float(np.percentile(times, 95)) if times else None,
              "cabin_event_validation": "not measured by static images", "subject_independence": "not established for legacy datasets",
              "predictions": entries}
    if compare:
        ref_metrics = classification_metrics(truth, reference, classes)
        report["parity"] = {"reference": reference_backend, "maximum_probability_error": max_error,
                            "label_agreement": agreement / max(len(times), 1),
                            "reference_macro_f1": ref_metrics["macro_f1"],
                            "f1_drop_points": 100 * (ref_metrics["macro_f1"] - metrics["macro_f1"]),
                            "passed": bool(times) and agreement / len(times) >= .98 and ref_metrics["macro_f1"] - metrics["macro_f1"] <= .02}
    save_report(args.output, report)
    print(json.dumps({"metrics": metrics, "parity": report.get("parity")}, ensure_ascii=False), flush=True)
    return report


def read_annotations(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    identities = {}
    clips = {}
    valid = {"normal", "eyes_closed", "yawn", "unknown"}
    for row in rows:
        required = ("subject_id", "clip_id", "split", "lighting", "start", "end", "label")
        if any(not row.get(k) for k in required):
            raise ValueError("annotations require subject_id, clip_id, split, lighting, start, end, label")
        row["start"], row["end"] = float(row["start"]), float(row["end"])
        if not np.isfinite([row["start"], row["end"]]).all() or not 0 <= row["start"] < row["end"]:
            raise ValueError("invalid annotation interval")
        if row["label"] not in valid or row["split"] not in ("train", "val", "test"):
            raise ValueError("invalid annotation label/split")
        subject, clip, split = row["subject_id"], row["clip_id"], row["split"]
        if subject in identities and identities[subject] != split:
            raise ValueError("subject leaked across train/val/test")
        if clip in clips and clips[clip] != (subject, split, row["lighting"]):
            raise ValueError("clip metadata inconsistent")
        identities[subject] = split
        clips[clip] = (subject, split, row["lighting"])
    # Eye and yawn labels may overlap. Same-label intervals must not overlap.
    for clip in clips:
        for label in valid:
            group = sorted((r for r in rows if r["clip_id"] == clip and r["label"] == label), key=lambda r: r["start"])
            if any(a["end"] > b["start"] for a, b in zip(group, group[1:])):
                raise ValueError("duplicate/overlapping same-label intervals")
        normals = [r for r in rows if r["clip_id"] == clip and r["label"] == "normal"]
        events = [r for r in rows if r["clip_id"] == clip and r["label"] != "normal"]
        if any(max(a["start"], b["start"]) < min(a["end"], b["end"]) for a in normals for b in events):
            raise ValueError("normal interval overlaps an event")
        unknowns = [r for r in events if r["label"] == "unknown"]
        known = [r for r in events if r["label"] != "unknown"]
        if any(max(a["start"], b["start"]) < min(a["end"], b["end"]) for a in unknowns for b in known):
            raise ValueError("unknown interval overlaps a known event")
    return rows


def evaluate_session(frames_path, annotations_path, clip_id, output, config):
    annotations = [r for r in read_annotations(annotations_path) if r["clip_id"] == clip_id]
    if not annotations:
        raise ValueError("clip has no annotations")
    metadata_path = Path(frames_path).with_suffix(".jsonl")
    with metadata_path.open(encoding="utf-8") as stream:
        metadata = next((r for line in stream if (r := json.loads(line)).get("event") == "session_start"), None)
    if metadata is None or metadata.get("live") is not False:
        raise ValueError("event evaluation requires replay metadata for a recorded clip")
    if metadata.get("config_sha256") != config.fingerprint():
        raise ValueError("evaluation config/models differ from the recorded session")
    if Path(metadata.get("source", "")).name != Path(clip_id).name:
        raise ValueError("replay source does not match clip_id")
    with Path(frames_path).open(encoding="utf-8", newline="") as stream:
        frames = list(csv.DictReader(stream))
    if not frames:
        raise ValueError("empty frame log")
    for row in frames:
        row["timestamp"] = float(row["timestamp"])
        row["latency_ms"] = float(row["latency_ms"])
        if not np.isfinite([row["timestamp"], row["latency_ms"]]).all() or row["timestamp"] < 0 or row["latency_ms"] < 0:
            raise ValueError("invalid frame timestamp/latency")
    if any(a["timestamp"] >= b["timestamp"] for a, b in zip(frames, frames[1:])):
        raise ValueError("frame log timestamps are not monotonic")
    closed = [r for r in annotations if r["label"] == "eyes_closed" and r["end"] - r["start"] >= config.monitor.eye_closed_seconds]
    yawns = [r for r in annotations if r["label"] == "yawn"]
    normal_seconds = sum(r["end"] - r["start"] for r in annotations if r["label"] == "normal")
    # Refuse short or partial replay logs instead of reporting unobserved intervals as correct.
    if min(r["start"] for r in annotations) < frames[0]["timestamp"] - .25 or max(r["end"] for r in annotations) > frames[-1]["timestamp"] + .25:
        raise ValueError("annotations extend beyond recorded frame log")
    # Match distinct confirmations, not one lingering yawn/alarm to several labels.
    closure_confirmations, yawn_confirmations = [], []
    previous_closure, previous_yawn_count = False, 0
    for frame in frames:
        closure = frame["alert"] == "1" and "eyes_closed_too_long" in frame["reasons"] and "recovering" not in frame["reasons"]
        if closure and not previous_closure:
            closure_confirmations.append(frame)
        count = int(frame["yawn_count"])
        if count > previous_yawn_count and frame["yawn_state"] == "yawn":
            yawn_confirmations.append(frame)
        previous_closure, previous_yawn_count = closure, count
    delays, closure_hits, yawn_hits = [], 0, 0
    for event in closed:
        expected = event["start"] + config.monitor.eye_closed_seconds
        hits = [f for f in closure_confirmations if expected <= f["timestamp"] <= event["end"]]
        if hits:
            closure_hits += 1
            delays.append((hits[0]["timestamp"] - expected) * 1000 + float(hits[0]["latency_ms"]))
            closure_confirmations.remove(hits[0])
    for event in yawns:
        hits = [f for f in yawn_confirmations if event["start"] <= f["timestamp"] <= event["end"]]
        if hits:
            yawn_hits += 1
            yawn_confirmations.remove(hits[0])
    false_alarms = 0
    last_alert = False
    for frame in frames:
        active = frame["alert"] == "1"
        if active and not last_alert and any(r["label"] == "normal" and r["start"] <= frame["timestamp"] < r["end"] for r in annotations):
            false_alarms += 1
        last_alert = active
    rate = false_alarms * 3600 / normal_seconds if normal_seconds else None
    recall = closure_hits / len(closed) if closed else None
    report = {"type": "annotated_clip", "clip_id": clip_id, "subject_id": annotations[0]["subject_id"],
              "split": annotations[0]["split"], "lighting": annotations[0]["lighting"],
              "config_sha256": config.fingerprint(), "frames_sha256": sha256(frames_path), "annotations_sha256": sha256(annotations_path),
              "source_sha256": metadata.get("source_sha256"), "backend": metadata.get("backend"),
              "frames": len(frames),
              "closure_events": len(closed), "closure_hits": closure_hits, "closure_recall": recall,
              "yawn_events": len(yawns), "yawn_hits": yawn_hits, "yawn_event_recall": yawn_hits / len(yawns) if yawns else None,
              "normal_seconds": normal_seconds, "false_alarm_count": false_alarms, "false_alarms_per_hour": rate,
              "reaction_p95_ms": float(np.percentile(delays, 95)) if delays else None,
              "reaction_delays_ms": delays, "reaction_note": "Decision time only; physical buzzer/ACK delay requires an ESP32 bench test.",
              "unknown_frame_fraction": sum(f["state"] == "UNKNOWN" for f in frames) / len(frames),
              "latency_p95_ms": float(np.percentile([float(f["latency_ms"]) for f in frames], 95)),
              "acceptance": "requires aggregate >=5 subjects, >=2 held-out test subjects, >=30 closure and yawn events, >=2 normal hours"}
    save_report(output, report)
    return report


def evaluate_study(reports_directory, annotations_path, output):
    """Aggregate held-out event evidence without averaging percentages or p95s."""
    annotations = read_annotations(annotations_path)
    annotations_hash = sha256(annotations_path)
    test_clips = {r["clip_id"]: r for r in annotations if r["split"] == "test"}
    reports, seen, fingerprint = [], set(), None
    for path in sorted(Path(reports_directory).glob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("type") != "annotated_clip" or report.get("split") != "test":
            continue
        clip = report["clip_id"]
        if clip in seen:
            raise ValueError("duplicate evaluated clip")
        if clip not in test_clips or report["annotations_sha256"] != annotations_hash:
            raise ValueError("report does not match this study's held-out annotations")
        expected = test_clips[clip]
        if report["subject_id"] != expected["subject_id"] or report["lighting"] != expected["lighting"]:
            raise ValueError("report subject/lighting differs from annotations")
        if fingerprint is not None and fingerprint != report["config_sha256"]:
            raise ValueError("study reports use different frozen configs/models")
        seen.add(clip)
        fingerprint = report["config_sha256"]
        reports.append(report)
    if not reports:
        raise ValueError("no held-out annotated_clip reports")
    def aggregate(rows):
        values = {k: sum(r[k] for r in rows) for k in ("closure_events", "closure_hits", "yawn_events", "yawn_hits", "normal_seconds", "false_alarm_count", "frames")}
        for kind in ("closure", "yawn"):
            values[kind + "_recall"] = values[kind + "_hits"] / values[kind + "_events"] if values[kind + "_events"] else None
        values["false_alarms_per_hour"] = values["false_alarm_count"] * 3600 / values["normal_seconds"] if values["normal_seconds"] else None
        delays = [value for row in rows for value in row["reaction_delays_ms"]]
        values["decision_reaction_p95_ms"] = float(np.percentile(delays, 95)) if delays else None
        values["unknown_frame_fraction"] = sum(r["frames"] * r["unknown_frame_fraction"] for r in rows) / max(values["frames"], 1)
        return values
    overall = aggregate(reports)
    subjects = sorted({r["subject_id"] for r in reports})
    lighting = sorted({r["lighting"] for r in reports})
    enough = (len({r["subject_id"] for r in annotations}) >= 5 and len(subjects) >= 2
              and overall["closure_events"] >= 30 and overall["yawn_events"] >= 30
              and overall["normal_seconds"] >= 7200 and seen == set(test_clips))
    meets_events = (enough and overall["closure_recall"] >= .90 and overall["false_alarms_per_hour"] <= 1)
    result = {"type": "held_out_event_study", "config_sha256": fingerprint, "annotations_sha256": annotations_hash,
              "complete_data": enough, "event_criteria_met": meets_events, "overall": overall,
              "by_subject": {s: aggregate([r for r in reports if r["subject_id"] == s]) for s in subjects},
              "by_lighting": {light: aggregate([r for r in reports if r["lighting"] == light]) for light in lighting},
              "evaluated_clips": sorted(seen), "missing_test_clips": sorted(set(test_clips) - seen),
              "system_acceptance": "Separate classification, RKNN parity, live-board performance, physical buzzer and 2-hour operation evidence required."}
    save_report(output, result)
    return result
