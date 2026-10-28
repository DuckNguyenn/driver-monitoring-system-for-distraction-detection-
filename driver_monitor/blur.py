"""Offline blur augmentation and conservative quality-gate calibration.

Images remain BGR uint8 at native crop resolution. Live preprocessing and
UNKNOWN handling are not changed by this module.
"""
import hashlib
import math
from dataclasses import replace

import cv2
import numpy as np

from .vision import assess_quality


def motion_kernel(length, angle):
    if not isinstance(length, int) or length < 3 or length > 15 or length % 2 == 0:
        raise ValueError("motion length must be an odd integer from 3 to 15")
    if not math.isfinite(angle):
        raise ValueError("motion angle must be finite")
    kernel = np.zeros((length, length), np.float32)
    kernel[length // 2, :] = 1
    transform = cv2.getRotationMatrix2D(((length - 1) / 2,) * 2, angle, 1)
    kernel = cv2.warpAffine(kernel, transform, (length, length))
    return kernel / kernel.sum()


def apply_blur(image, parameters):
    if image is None or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or not image.size:
        raise ValueError("blur requires a nonempty BGR uint8 crop")
    if parameters["kind"] == "base":
        return image.copy()
    if parameters["kind"] == "gaussian":
        sigma = float(parameters["sigma"])
        if not math.isfinite(sigma) or not 0 < sigma <= 3:
            raise ValueError("gaussian sigma must be in (0, 3]")
        size = 2 * math.ceil(3 * sigma) + 1
        return cv2.GaussianBlur(image, (size, size), sigma, borderType=cv2.BORDER_REPLICATE)
    if parameters["kind"] == "motion":
        kernel = motion_kernel(parameters["length"], parameters["angle"])
        return cv2.filter2D(image, -1, kernel, borderType=cv2.BORDER_REPLICATE)
    raise ValueError("unknown blur kind")


def training_blurs(split, parent_id, seed=42):
    """Reproducible native-pixel strengths; siblings inherit the parent's split.

    Validation/test originals are untouched. Fixed stress variants below are
    explicitly identified as evaluation data, never training augmentation.
    """
    if split not in ("train", "val", "test", "regression"):
        raise ValueError("invalid data split")
    if split != "train":
        return []
    digest = hashlib.sha256(f"{seed}:{parent_id}".encode()).digest()
    return [
        {"kind": "gaussian", "sigma": round(.45 + digest[0] / 255 * .60, 4)},
        {"kind": "motion", "length": 3 if digest[1] % 2 == 0 else 5,
         "angle": (-60, -30, 0, 30, 60, 90)[digest[2] % 6]},
    ]


STRESS_BLURS = (
    {"kind": "gaussian", "sigma": .75},
    {"kind": "motion", "length": 3, "angle": 30},
)


def exclude_split_duplicates(records):
    """Exclude whole lower-priority parents, including all augmented siblings.

    Preserves existing assignments instead of re-splitting known holdouts.
    Photo families, raw pixels and preprocessed pixels are checked. This does
    not establish independence between different photos of the same person.
    """
    priority = {"train": 0, "val": 1, "test": 2, "regression": 3}
    owners, labels = {}, {}

    def keys(row):
        values = [row.get("sha256"), row.get("input_sha256")]
        if row.get("photo_family"):
            values.append(f"{row['source']}:{row['photo_family']}")
        return [v for v in values if v]

    for row in records:
        if row["split"] not in priority:
            raise ValueError("invalid split")
        digest = row.get("input_sha256")
        if digest and digest in labels and labels[digest] != row["label"]:
            raise ValueError("conflicting labels for identical classifier pixels")
        if digest:
            labels[digest] = row["label"]
        for key in keys(row):
            owners[key] = max(owners.get(key, -1), priority[row["split"]])
    excluded = {r["parent_id"] for r in records if any(
        priority[r["split"]] < owners[key] for key in keys(r))}
    return [r for r in records if r["parent_id"] not in excluded], sorted(excluded)


def gate_metrics(records, probabilities, config, classes, positive):
    """Count abstentions in the denominator; blocking every frame cannot pass.

    Errors are counted at the live confidence cutoffs, in addition to argmax
    classification. A missed/UNKNOWN positive lowers recall. Negative-class
    confusion at high confidence is a potential false warning, not an event.
    """
    thresholds = {c: (.8 if positive == "Closed" else (.7 if c == positive else .65)) for c in classes}
    count = len(records)
    accepted = []
    for row in records:
        usable = (row.get("geometry_valid", True) and row.get("metrics") is not None
                  and assess_quality(row["metrics"], config) == "usable")
        accepted.append(bool(usable))
    result = {"samples": count, "accepted": sum(accepted), "blocked": count - sum(accepted)}
    result["quality_unknown_rate"] = result["blocked"] / max(count, 1)
    result["classes"] = {}
    confident = 0
    for index, label in enumerate(classes):
        chosen = [(r, a) for r, a in zip(records, accepted) if r["label"] == label]
        hits = sum(a and probabilities[r["feature"], index] >= thresholds[label] for r, a in chosen)
        false = sum(a and r["label"] != label and probabilities[r["feature"], index] >= thresholds[label]
                    for r, a in zip(records, accepted))
        result["classes"][label] = {"samples": len(chosen), "correct_confident": int(hits),
                                   "recall_including_unknown": hits / max(len(chosen), 1),
                                   "false_confident": int(false)}
        confident += hits + false
    result["decision_unknown_rate"] = 1 - confident / max(count, 1)
    return result


def calibrate_quality(records_by_kind, baseline_p, candidate_p, config,
                      face_grid=(20., 18., 16., 14., 12.), eye_grid=(6., 5., 4., 3.)):
    """Select only from real, unaugmented validation observations.

    The grid preserves darkness/overexposure guards. Every classifier/class
    must retain recall and false-confident counts. Test/regression/stress rows
    are rejected, rather than silently used to tune a live threshold.
    """
    classes = {"eye": ["Closed", "Open"], "yawn": ["no_yawn", "yawn"]}
    positives = {"eye": "Closed", "yawn": "yawn"}
    if set(records_by_kind) != set(classes):
        raise ValueError("calibration requires both eye and yawn validation")
    for rows in records_by_kind.values():
        if not rows or any(r["split"] != "val" or r["variant"] != "base" for r in rows):
            raise ValueError("calibration accepts only real base validation samples")
    baseline = {kind: gate_metrics(rows, baseline_p[kind], config, classes[kind], positives[kind])
                for kind, rows in records_by_kind.items()}
    trials, selected, best = [], None, -1
    for face in face_grid:
        for eye in eye_grid:
            if not 0 < face <= config.min_sharpness or not 0 < eye <= config.min_eye_sharpness:
                raise ValueError("calibration grid must be positive and no higher than baseline")
            trial_config = replace(config, min_sharpness=face, min_eye_sharpness=eye)
            scores = {kind: gate_metrics(rows, candidate_p[kind], trial_config, classes[kind], positives[kind])
                      for kind, rows in records_by_kind.items()}
            reasons = []
            by_source = {}
            for kind, score in scores.items():
                for label, c in score["classes"].items():
                    b = baseline[kind]["classes"][label]
                    if c["samples"] < 10:
                        reasons.append(f"insufficient_{kind}_{label}")
                    if c["recall_including_unknown"] + 1e-12 < b["recall_including_unknown"]:
                        reasons.append(f"recall_regression_{kind}_{label}")
                    if c["false_confident"] > b["false_confident"]:
                        reasons.append(f"false_confident_increase_{kind}_{label}")
                if score["decision_unknown_rate"] > baseline[kind]["decision_unknown_rate"] + 1e-12:
                    reasons.append(f"unknown_increase_{kind}")
                by_source[kind] = {}
                for group in sorted({r.get("group", "all") for r in records_by_kind[kind]}):
                    subset = [r for r in records_by_kind[kind] if r.get("group", "all") == group]
                    b = gate_metrics(subset, baseline_p[kind], config, classes[kind], positives[kind])
                    c = gate_metrics(subset, candidate_p[kind], trial_config, classes[kind], positives[kind])
                    by_source[kind][group] = {"baseline": b, "candidate": c}
                    for label, value in c["classes"].items():
                        previous = b["classes"][label]
                        if value["recall_including_unknown"] + 1e-12 < previous["recall_including_unknown"]:
                            reasons.append(f"source_recall_regression_{kind}_{group}_{label}")
                        if value["false_confident"] > previous["false_confident"]:
                            reasons.append(f"source_false_confident_increase_{kind}_{group}_{label}")
            gain = sum(baseline[k]["blocked"] - scores[k]["blocked"] for k in scores)
            # Higher thresholds win ties, avoiding an unsupported extra relaxation.
            trial = {"min_sharpness": face, "min_eye_sharpness": eye,
                     "passed": not reasons, "rejection_reasons": reasons,
                     "additional_accepted_validation_samples": gain, "metrics": scores, "by_source": by_source}
            trials.append(trial)
            if not reasons and gain > best:
                selected, best = trial, gain
    return {"selection_split": "val", "synthetic_data_used_for_gate_selection": False,
            "baseline": baseline, "trials": trials, "selected": selected,
            "independent_camera_acceptance": False}
