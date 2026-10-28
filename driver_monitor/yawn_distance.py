"""Native camera ROI augmentation and reviewed, clip-separated yawn data.

Inference continues to use models.prepare_rgb/prepare_tensor. Resolution loss
and blur are training-only operations, applied before that shared transform.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from .blur import apply_blur
from .config import ROOT
from .models import prepare_rgb, sha256

CLASSES = ("no_yawn", "yawn")
DISTANCES = ("near", "medium", "far")
FIELDS = ("clip_id", "subject_id", "capture_group", "split", "distance", "lighting",
          "start", "end", "label", "action", "reviewed")


@dataclass(frozen=True)
class DistanceAugmentation:
    factors: tuple = (.75, .50, .35)
    downsample_probability: float = .50
    gaussian_probability: float = .25
    gaussian_sigma: tuple = (.35, .70)
    motion_probability: float = .15
    motion_length: int = 3
    min_short_side: int = 24

    def __post_init__(self):
        if not self.factors or any(not math.isfinite(f) or not 0 < f < 1 for f in self.factors):
            raise ValueError("downsample factors must be in (0, 1)")
        for p in (self.downsample_probability, self.gaussian_probability, self.motion_probability):
            if not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError("augmentation probabilities must be in [0, 1]")
        if len(self.gaussian_sigma) != 2 or not 0 < self.gaussian_sigma[0] <= self.gaussian_sigma[1] <= 1:
            raise ValueError("use a mild gaussian sigma range in (0, 1]")
        if self.motion_length != 3 or self.min_short_side < 16:
            raise ValueError("use mild 3-pixel motion and a minimum native side >=16")


def downsample_native(crop, factor, min_short_side=24):
    """Reduce native ROI detail with AREA; never distort its aspect ratio."""
    if not math.isfinite(factor) or not 0 < factor <= 1:
        raise ValueError("invalid downsampling factor")
    h, w = crop.shape[:2]
    scale = min(1., max(factor, min_short_side / min(h, w)))
    return cv2.resize(crop, (max(1, round(w * scale)), max(1, round(h * scale))),
                      interpolation=cv2.INTER_AREA) if scale < 1 else crop.copy()


def training_rgb(crop, spec, split, recipe, rng):
    """Keep val/test exact; random training siblings keep their parent's split."""
    if split not in ("train", "val", "test", "regression"):
        raise ValueError("invalid split")
    if split != "train":
        return prepare_rgb(crop, spec)
    native = crop.copy()
    if rng.random() < recipe.downsample_probability:
        native = downsample_native(native, float(rng.choice(recipe.factors)), recipe.min_short_side)
    if rng.random() < recipe.gaussian_probability:
        native = apply_blur(native, {"kind": "gaussian", "sigma": float(rng.uniform(*recipe.gaussian_sigma))})
    if rng.random() < recipe.motion_probability:
        native = apply_blur(native, {"kind": "motion", "length": recipe.motion_length,
                                     "angle": float(rng.choice((0, 30, 60, 90)))})
    return prepare_rgb(native, spec)


def preview_views(crop, spec, recipe):
    views = {"original": prepare_rgb(crop, spec)}
    for f in recipe.factors:
        native = downsample_native(crop, f, recipe.min_short_side)
        views[f"downsample_{f:g}"] = prepare_rgb(native, spec)
        blurred = apply_blur(native, {"kind": "gaussian", "sigma": recipe.gaussian_sigma[0]})
        views[f"downsample_{f:g}_blur"] = prepare_rgb(blurred, spec)
    views["motion_3"] = prepare_rgb(apply_blur(crop, {"kind": "motion", "length": 3, "angle": 30}), spec)
    return views


def json_save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def locked_video_registry(directory=ROOT / "data_reviews"):
    """Recognize held-out captures by bytes, even if somebody renames a file."""
    result = {}
    for path in Path(directory).glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("training_allowed") is False or data.get("checkpoint_selection_allowed") is False:
            if data.get("video_sha256"):
                result[data["video_sha256"]] = path.name
    return result


def read_distance_annotations(path, videos, split_mode="clip", registry=None, require_coverage=True,
                              *, active_distances=DISTANCES, required_splits=("train", "val")):
    if (not active_distances or len(set(active_distances)) != len(active_distances) or
            any(d not in DISTANCES for d in active_distances)):
        raise ValueError("invalid active distances")
    if not required_splits or any(s not in ("train", "val") for s in required_splits):
        raise ValueError("invalid required camera splits")
    if split_mode not in ("clip", "subject"):
        raise ValueError("split_mode must be clip or subject")
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("annotation CSV is missing required columns")
        rows = list(reader)
    if not rows:
        raise ValueError("No reviewed camera data yet; record and annotate new distance clips first.")
    clips, assignments = defaultdict(list), {}
    videos = Path(videos).resolve()
    registry = locked_video_registry() if registry is None else registry
    for row in rows:
        if any(not row[k].strip() for k in FIELDS):
            raise ValueError("annotation fields must be filled, including action and reviewed")
        if row["reviewed"].strip().casefold() not in ("true", "yes", "1"):
            raise ValueError("Prompts are not ground truth: review every labeled interval first.")
        if row["split"] not in ("train", "val", "test") or row["distance"] not in DISTANCES or row["label"] not in CLASSES:
            raise ValueError("invalid split, distance or yawn label")
        start, end = float(row["start"]), float(row["end"])
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end:
            raise ValueError("invalid annotation interval")
        row["start"], row["end"] = start, end
        for key in ("clip_id", "capture_group") + (("subject_id",) if split_mode == "subject" else ()):
            owner = (key, row[key])
            if owner in assignments and assignments[owner] != row["split"]:
                raise ValueError(f"{key} leakage across splits: {row[key]}")
            assignments[owner] = row["split"]
        clips[row["clip_id"]].append(row)
    seen_videos = {}
    for name, intervals in clips.items():
        clip = (videos / name).resolve()
        if not clip.is_relative_to(videos):
            raise ValueError("clip_id must stay inside videos directory")
        digest = sha256(clip)
        if digest in registry and intervals[0]["split"] != "test":
            raise ValueError(f"Locked diagnostic cannot train or select a checkpoint: {registry[digest]}")
        split = intervals[0]["split"]
        if digest in seen_videos and seen_videos[digest] != split:
            raise ValueError("identical video bytes leaked across splits")
        seen_videos[digest] = split
        ordered = sorted(intervals, key=lambda r: r["start"])
        if any(a["end"] > b["start"] for a, b in zip(ordered, ordered[1:])):
            raise ValueError(f"overlapping yawn labels in {name}")
        for key in ("subject_id", "capture_group", "distance", "lighting"):
            if len({r[key] for r in intervals}) != 1:
                raise ValueError(f"inconsistent {key} within clip: {name}")
    # Validate all assignments/locked bytes before restricting the experiment's scope.
    rows = [r for r in rows if r["distance"] in active_distances]
    if require_coverage:
        coverage = {(r["split"], r["distance"], r["label"]) for r in rows}
        missing = [(s, d, c) for s in required_splits for d in active_distances for c in CLASSES if (s, d, c) not in coverage]
        if missing:
            raise ValueError(f"Missing reviewed distance/class coverage: {missing}")
        for split in required_splits:
            actions = {r["action"] for r in rows if r["split"] == split and r["label"] == "no_yawn"}
            if not {"normal", "smile"}.issubset(actions):
                raise ValueError(f"{split} needs normal mouth and teeth-smile negatives")
    return rows


def verify_prepared_dataset(path, config, recipe):
    data = json.loads((Path(path) / "dataset.json").read_text(encoding="utf-8"))
    if data["runtime_config_sha256"] != config.fingerprint() or data["manifest_sha256"] != sha256(config.manifest):
        raise ValueError("runtime config/manifest changed; prepare again")
    if data["augmentation"] != json.loads(json.dumps(asdict(recipe))):
        raise ValueError("augmentation recipe changed; prepare again")
    for source in data["sources"]:
        if sha256(Path(source["file"])) != source["sha256"]:
            raise ValueError("dataset source changed; prepare again")
    for row in data["records"]:
        if row.get("file") and sha256(Path(path) / row["file"]) != row["sha256"]:
            raise ValueError("native crop bytes changed; prepare again")
    if any(r["split"] != "train" and r.get("augmentation", "original") != "original" for r in data["records"]):
        raise ValueError("augmented holdout data")
    return data


def summarize(rows):
    return dict(Counter(f"{r['split']}/{r['distance']}/{r['label']}/{r['action']}" for r in rows))
