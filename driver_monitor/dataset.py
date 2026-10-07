"""Subject-separated video crops, train-only calibration and optional fine-tuning."""
import csv
import json
from pathlib import Path
import cv2
from .capture import Capture
from .evaluation import read_annotations
from .models import read_manifest, prepare_rgb, sha256
from .vision import Vision, orient_frame


def prepare_dataset(annotations_path, videos, output, config):
    annotations = read_annotations(annotations_path)
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output dataset is nonempty; use a new directory")
    output.mkdir(parents=True, exist_ok=True)
    videos = Path(videos).resolve()
    vision = Vision(config)
    manifest = read_manifest(config.manifest)
    records, calibration = [], {"eye": [], "yawn": []}
    groups = {}
    for row in annotations:
        groups.setdefault(row["clip_id"], []).append(row)
    for clip_id, intervals in groups.items():
        clip = (videos / clip_id).resolve()
        if not clip.is_relative_to(videos):
            raise ValueError("clip_id must stay inside the video directory")
        capture = Capture(clip)
        if capture.live:
            capture.close()
            raise ValueError("dataset preparation requires a recorded video")
        last_sample = float("-inf")
        try:
            while True:
                packet = capture.read()
                if packet is None:
                    break
                if packet.timestamp - last_sample < .20:
                    continue  # avoid thousands of near-identical adjacent frames
                last_sample = packet.timestamp
                active = [r for r in intervals if r["start"] <= packet.timestamp < r["end"]]
                if not active or any(r["label"] == "unknown" for r in active):
                    continue
                result = vision.observe(orient_frame(packet.image, config.rotation_degrees))
                if result.quality != "usable":
                    continue
                labels = {r["label"] for r in active}
                # Unannotated channels do not receive invented negative labels.
                tasks = []
                if "normal" in labels or "eyes_closed" in labels:
                    label = "Closed" if "eyes_closed" in labels else "Open"
                    tasks += [("eye", label, result.crops[0]), ("eye", label, result.crops[1])]
                if "normal" in labels or "yawn" in labels:
                    tasks.append(("yawn", "yawn" if "yawn" in labels else "no_yawn", result.crops[2]))
                for number, (kind, label, image) in enumerate(tasks):
                    metadata = active[0]
                    name = f"{Path(clip_id).stem}_{packet.index:07d}_{number}.png"
                    destination = output / kind / metadata["split"] / label / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        raise ValueError("clip filenames collide; use distinct clip stems")
                    if not cv2.imwrite(str(destination), image):
                        raise OSError("could not write crop")
                    record = {"kind": kind, "label": label, "split": metadata["split"], "subject_id": metadata["subject_id"],
                              "clip_id": clip_id, "lighting": metadata["lighting"], "timestamp": packet.timestamp,
                              "file": str(destination.relative_to(output)).replace("\\", "/"), "sha256": sha256(destination)}
                    records.append(record)
                    if metadata["split"] == "train":
                        # Toolkit reads RGB images; size/crop are identical to runtime.
                        rgb = prepare_rgb(image, manifest["classifiers"][kind])
                        cal_path = output / "calibration" / kind / name
                        cal_path.parent.mkdir(parents=True, exist_ok=True)
                        cv2.imwrite(str(cal_path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                        calibration[kind].append({**record, "file": str(cal_path.relative_to(output)).replace("\\", "/"), "sha256": sha256(cal_path)})
        finally:
            capture.close()
    if not records:
        raise ValueError("no usable annotated crops; inspect video, ROI and annotations")
    (output / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    for kind, rows in calibration.items():
        (output / f"{kind}.calibration.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Prepared {len(records)} subject-separated crops: {output}")


def train(args):
    import os
    from .config import ROOT
    cache = ROOT / ".cache/ultralytics"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(cache))
    from ultralytics import YOLO
    root = Path(args.data).resolve()
    records = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    selected = [r for r in records if r["kind"] == args.name]
    assignments = {}
    hashes = {}
    for row in selected:
        subject, split = row["subject_id"], row["split"]
        if subject in assignments and assignments[subject] != split:
            raise ValueError("subject leakage")
        if row["sha256"] in hashes and hashes[row["sha256"]] != split:
            raise ValueError("identical crops leaked across splits")
        assignments[subject], hashes[row["sha256"]] = split, split
    classes = ("Open", "Closed") if args.name == "eye" else ("no_yawn", "yawn")
    for split in ("train", "val", "test"):
        for label in classes:
            if not any(r["split"] == split and r["label"] == label for r in selected):
                raise ValueError(f"missing {split}/{label}")
    model = YOLO(str(Path(args.checkpoint).resolve()))
    if model.task != "classify":
        raise ValueError("fine-tuning requires a classification checkpoint")
    model.train(data=str(root / args.name), epochs=args.epochs, imgsz=224, batch=32, seed=42,
                patience=10, device=args.device, workers=0, project=str(Path(args.output).resolve()), name=args.name)
    # No test-set tuning or automatic replacement of deployed weights.
    print("Validate and export the new best checkpoint; keep the test set held out.")
