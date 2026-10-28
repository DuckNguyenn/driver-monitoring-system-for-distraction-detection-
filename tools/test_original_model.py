"""Test one classifier on runtime ROIs from a camera or video.

Uses models/manifest.json by default; --use-config-model selects the model
from the supplied runtime configuration. This diagnostic shows
raw probabilities, including low-quality crops, and does not run Monitor or
connect to ESP32. It saves a CSV for inspection, not an accuracy score.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

from driver_monitor.capture import Capture
from driver_monitor.config import load_config
from driver_monitor.models import Classifier, prepare_rgb, read_manifest, sha256
from driver_monitor.vision import Vision, orient_frame, quality_metrics


class SourceRecording:
    """Save the exact, unpainted source frames used for each CSV row."""
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            raise FileExistsError(f"Recording already exists: {self.path}")
        self.writer = None
        self.shape = None
        self.timestamps = []
        self.hashes = []

    def write(self, frame, seconds):
        if not np.isfinite(seconds) or seconds < 0 or (self.timestamps and seconds <= self.timestamps[-1]):
            raise ValueError("Recording timestamps must increase")
        if self.writer is None:
            self.shape = frame.shape
            self.writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*"FFV1"),
                                         30., (frame.shape[1], frame.shape[0]))
            if not self.writer.isOpened():
                self.writer.release()
                self.writer = None
                raise RuntimeError("Lossless FFV1 writer unavailable")
        if frame.shape != self.shape:
            raise ValueError("Camera resolution changed during recording")
        self.writer.write(frame)
        self.timestamps.append(float(seconds))
        self.hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())

    def close(self, metadata):
        if self.writer is not None:
            self.writer.release()
            self.writer = None
        if not self.timestamps:
            return
        timestamps = {"timestamps_seconds": self.timestamps, "frame_sha256": self.hashes,
                      "frame_hash_format": "BGR uint8 HWC bytes before rotation or overlays",
                      "note": "FFV1 header nominal 30 FPS; use exact source timestamps"}
        self.path.with_suffix(".timestamps.json").write_text(json.dumps(timestamps, indent=2), encoding="utf-8")
        metadata = {**metadata, "recording": str(self.path), "codec": "FFV1",
                    "frames": len(self.timestamps), "frame_shape": list(self.shape),
                    "source_duration_seconds": self.timestamps[-1],
                    "video_sha256": sha256(self.path),
                    "ground_truth_reviewed": False}
        self.path.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def draw(preview, result, predictions, name, elapsed, latency, model_origin="Original"):
    for index in ((0, 1) if name == "eye" else (2,)):
        if result.boxes:
            x1, y1, x2, y2 = result.boxes[index]
            cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 220, 0), 2)
    rows = [f"{model_origin} {name} model | RAW probabilities",
            f"Quality: {result.quality} | t:{elapsed:.2f}s | inference:{latency:.1f}ms"]
    if result.crops is not None:
        face = result.crops[2]
        rows.append(f"Face ROI: {face.shape[1]}x{face.shape[0]}px | {100*face.shape[1]/preview.shape[1]:.1f}% frame width")
    if name == "eye":
        rows.append(f"Eye quality: {result.eye_quality}")
    for index, values in enumerate(predictions):
        title = f"Eye {index + 1}" if name == "eye" else "Face"
        guess = max(values, key=values.get)
        rows.append(f"{title}: {guess} | " + " | ".join(f"{k}:{v:.3f}" for k, v in values.items()))
    if not predictions:
        rows.append("No valid ROI; probabilities unavailable")
    cv2.rectangle(preview, (0, 0), (preview.shape[1], 26 * (len(rows) + 1)), (20, 20, 20), -1)
    for index, text in enumerate(rows):
        cv2.putText(preview, text, (8, 22 + index * 26), cv2.FONT_HERSHEY_SIMPLEX,
                    .46, (0, 235, 235), 1, cv2.LINE_AA)
    cv2.putText(preview, "Q / Esc: finish", (8, preview.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, .45, (240, 240, 240), 1, cv2.LINE_AA)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", choices=("eye", "yawn"), required=True)
    parser.add_argument("--source", default="0", help="OpenCV camera index or video path")
    parser.add_argument("--backend", choices=("torch", "onnx"), default="torch")
    parser.add_argument("--config", default=str(ROOT / "configs/camera_pc.yaml"), help="ROI/quality settings; model selected only with --use-config-model")
    parser.add_argument("--use-config-model", action="store_true", help="Test the classifier referenced by --config instead of the original checkpoint")
    parser.add_argument("--inspect-model", action="store_true", help="Show the exact RGB 224x224 inputs")
    parser.add_argument("--record", action="store_true", help="Save clean FFV1 camera/video frames with exact timestamps and hashes")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--realtime", action="store_true", help="Pace video playback by source timestamps")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--duration", type=float, default=0, help="Wall-clock seconds; zero means unlimited")
    parser.add_argument("--output-dir", default=str(ROOT / "reports/original_model_check"))
    args = parser.parse_args(argv)
    if args.max_frames < 0 or not np.isfinite(args.duration) or args.duration < 0:
        parser.error("max-frames and duration must be nonnegative")
    config = load_config(args.config, backend=args.backend,
                         **({} if args.use_config_model else {"manifest": ROOT / "models/manifest.json"}))
    model_origin = "Runtime" if args.use_config_model else "Original"
    spec = read_manifest(config.manifest)["classifiers"][args.name]
    blob = spec["artifacts"][args.backend]
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + args.name
    csv_path = output / (stem + ".csv")
    slots = 2 if args.name == "eye" else 1
    columns = [f"roi{i + 1}_{label}" for i in range(slots) for label in spec["classes"]]
    box_columns = [f"roi{i + 1}_{coordinate}" for i in range(slots) for coordinate in ("x1", "y1", "x2", "y2")]
    crop_columns = [f"roi{i + 1}_{metric}" for i in range(slots)
                    for metric in ("width", "height", "sharpness", "brightness_median")]
    input_hash_columns = [f"roi{i + 1}_input_sha256" for i in range(slots)] if args.record else []
    capture = model = None
    recording = SourceRecording(csv_path.with_suffix(".avi")) if args.record else None
    error = None
    frames = predicted_frames = 0
    started = None
    window = f"{model_origin} {args.name} model"
    try:
        model = Classifier(config.manifest, args.name, args.backend, config.cpu_threads)
        model.predict(np.zeros((224, 224, 3), np.uint8))  # warm-up before camera acquisition
        vision = Vision(config)
        print(f"Model: {(config.manifest.parent / blob['file']).resolve()}", flush=True)
        print(f"Classes: {spec['classes']} | backend: {args.backend}", flush=True)
        print("Raw classifier check; image quality is reported separately. Q / Esc to stop.", flush=True)
        capture = Capture(args.source, config.width, config.height)
        started = time.monotonic()
        origin = None
        with csv_path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["frame", "recording_frame", "source_seconds",
                "frame_width", "frame_height", "face_crop_width", "face_crop_height",
                "face_width_fraction", "face_sharpness", "eye_sharpness_min", "quality",
                "eye_quality", "inference_ms", "face_min_side_pixels", "face_detector_confidence",
                *box_columns, *crop_columns, *columns, *input_hash_columns])
            writer.writeheader()
            while not args.duration or time.monotonic() - started < args.duration:
                packet = capture.read()
                if packet is None:
                    if capture.error:
                        raise RuntimeError(capture.error)
                    if capture.eof:
                        break
                    continue
                if origin is None:
                    origin = packet.timestamp
                elapsed = packet.timestamp - origin
                if args.realtime and not capture.live:
                    remaining = elapsed - (time.monotonic() - started)
                    while remaining > 0 and (not args.duration or time.monotonic() - started < args.duration):
                        time.sleep(min(remaining, .05))
                        remaining = elapsed - (time.monotonic() - started)
                frame = orient_frame(packet.image, config.rotation_degrees)
                result = vision.observe(frame, packet.timestamp)
                if recording is not None:
                    recording.write(packet.image, elapsed)
                crops = [] if result.crops is None else list(result.crops[:2] if args.name == "eye" else result.crops[2:3])
                inference_started = time.perf_counter()
                values = [model.predict(crop) for crop in crops]
                latency = (time.perf_counter() - inference_started) * 1000 if values else 0.0
                row = {"frame": packet.index, "source_seconds": elapsed,
                       "quality": result.quality, "eye_quality": result.eye_quality,
                       "inference_ms": latency if values else None,
                       "recording_frame": frames if recording is not None else None,
                       "frame_width": frame.shape[1], "frame_height": frame.shape[0],
                       "face_sharpness": result.metrics.get("sharpness"),
                       "eye_sharpness_min": result.metrics.get("eye_sharpness_min"),
                       "face_min_side_pixels": result.metrics.get("face_min_side_pixels"),
                       "face_detector_confidence": result.confidence}
                if result.crops is not None:
                    face = result.crops[2]
                    row.update(face_crop_width=face.shape[1], face_crop_height=face.shape[0],
                               face_width_fraction=face.shape[1] / frame.shape[1])
                for index, probabilities in enumerate(values):
                    row.update({f"roi{index + 1}_{label}": p for label, p in probabilities.items()})
                    crop = crops[index]
                    row.update({f"roi{index + 1}_width": crop.shape[1], f"roi{index + 1}_height": crop.shape[0],
                                **{f"roi{index + 1}_{k}": v for k, v in quality_metrics(crop).items()
                                   if k in ("sharpness", "brightness_median")}})
                    if result.boxes:
                        box = result.boxes[index if args.name == "eye" else 2]
                        row.update({f"roi{index + 1}_{coordinate}": value
                                    for coordinate, value in zip(("x1", "y1", "x2", "y2"), box)})
                    if recording is not None:
                        row[f"roi{index + 1}_input_sha256"] = hashlib.sha256(prepare_rgb(crops[index], spec).tobytes()).hexdigest()
                writer.writerow(row)
                frames += 1
                predicted_frames += bool(values)
                if not args.headless:
                    preview = frame.copy()
                    draw(preview, result, values, args.name, elapsed, latency, model_origin)
                    cv2.imshow(window, preview)
                    if args.inspect_model:
                        if crops:
                            inputs = [prepare_rgb(crop, spec)[:, :, ::-1] for crop in crops]
                            panel = np.hstack(inputs)
                        else:
                            panel = np.zeros((224, 224 * slots, 3), np.uint8)
                            cv2.putText(panel, "No valid ROI", (8, 26), cv2.FONT_HERSHEY_SIMPLEX,
                                        .5, (240, 240, 240), 1, cv2.LINE_AA)
                        cv2.imshow("Actual model inputs 224x224", panel)
                    if cv2.waitKey(1) & 255 in (ord("q"), 27) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                        break
                if args.max_frames and frames >= args.max_frames:
                    break
    except KeyboardInterrupt:
        error = "interrupted_by_user"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if capture is not None:
            capture.close()
        if model is not None:
            model.close()
        if recording is not None:
            recording.close({"source": args.source, "classifier": args.name, "backend": args.backend,
                             "artifact_sha256": blob["sha256"], "csv": str(csv_path),
                             "manifest_sha256": sha256(config.manifest),
                             "classes": spec["classes"], "preprocessing": spec["preprocessing"],
                             "config_sha256": config.fingerprint(), "rotation_degrees": config.rotation_degrees,
                             "model_origin": model_origin.casefold(),
                             "roi_order": "driver_anatomical_left_right" if args.name == "eye" else "face",
                             "error": error})
        if not args.headless:
            cv2.destroyAllWindows()
    print(json.dumps({"classifier": args.name, "backend": args.backend,
                      "artifact_sha256": blob["sha256"], "frames": frames,
                      "frames_with_predictions": predicted_frames, "csv": str(csv_path),
                      "recording": str(recording.path) if recording is not None and recording.timestamps else None}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
