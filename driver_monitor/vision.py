"""YuNet detection, image quality, driver tracking and crops from original pixels."""
from dataclasses import dataclass, field
import cv2
import numpy as np

from .models import artifact_path, read_manifest
from .eye_motion import EyeMotion


@dataclass
class VisionResult:
    quality: str
    crops: tuple | None = None
    boxes: tuple = ()
    metrics: dict = field(default_factory=dict)
    confidence: float | None = None
    track_changed: bool = False
    eye_quality: str = "usable"


def orient_frame(frame, degrees):
    if not degrees:
        return frame
    return cv2.rotate(frame, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
                             270: cv2.ROTATE_90_COUNTERCLOCKWISE}[degrees])


def quality_metrics(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return {"brightness_median": float(np.median(gray)),
            "sharpness": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
            "overexposed_ratio": float(np.mean(gray > 235))}


def assess_quality(metrics, config):
    """Apply the same face/eye gates to live crops or recorded quality metrics."""
    if min(metrics["brightness_median"], metrics["eye_brightness_min"]) < config.min_brightness:
        return "too_dark"
    if metrics["overexposed_ratio"] > config.max_overexposed_ratio:
        return "overexposed"
    if (metrics["sharpness"] < config.min_sharpness
            or metrics["eye_sharpness_min"] < config.min_eye_sharpness):
        return "blurry"
    return "usable"


def crop_box(frame, cx, cy, width, height):
    h, w = frame.shape[:2]
    box = (max(0, int(cx - width / 2)), max(0, int(cy - height / 2)),
           min(w, int(np.ceil(cx + width / 2))), min(h, int(np.ceil(cy + height / 2))))
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        raise ValueError("crop outside frame")
    return frame[y1:y2, x1:x2].copy(), box


def face_crops(frame, face, config):
    x, y, w, h = map(float, face[:4])
    # FaceDetectorYN: 4:6 = anatomical right, 6:8 = anatomical left.
    # Observation retains the driver's anatomical left/right order.
    eyes = np.asarray(face[4:8], dtype=float).reshape(2, 2)[::-1]
    d = float(np.linalg.norm(eyes[0] - eyes[1]))
    if not np.isfinite(face).all() or d * config.eye_width_ratio < config.min_eye_width:
        raise ValueError("invalid or tiny eye landmarks")
    results = [crop_box(frame, *eye, d * config.eye_width_ratio, d * config.eye_height_ratio) for eye in eyes]
    results.append(crop_box(frame, x + w / 2, y + h / 2, w * (1 + 2 * config.face_margin), h * (1 + 2 * config.face_margin)))
    if any(crop.shape[0] < 4 or crop.shape[1] < config.min_eye_width for crop, _ in results[:2]):
        raise ValueError("truncated eye crop")
    return tuple(r[0] for r in results), tuple(r[1] for r in results)


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1])
    return intersection / max(area - intersection, 1e-9)


class Vision:
    def __init__(self, config):
        self.config = config
        spec = read_manifest(config.manifest)["detector"]
        path = artifact_path(config.manifest, spec)
        cv2.setNumThreads(config.cpu_threads)
        self.detector = cv2.FaceDetectorYN.create(str(path), "", (config.detector_size, config.detector_size),
                                                 config.detector_confidence, 0.3, 5000)
        self.previous_box = None
        self.eye_motion = EyeMotion(config)

    def observe(self, frame, timestamp=None):
        c = self.config
        h, w = frame.shape[:2]
        size = c.detector_size
        scale = min(size / w, size / h)
        rw, rh = round(w * scale), round(h * scale)
        ox, oy = (size - rw) // 2, (size - rh) // 2
        small = np.zeros((size, size, 3), np.uint8)
        small[oy:oy + rh, ox:ox + rw] = cv2.resize(frame, (rw, rh))
        _, found = self.detector.detect(small)
        candidates, roi_faces = [], []
        if found is not None:
            for face in found:
                row = face.astype(float).copy()
                row[0] = (row[0] - ox) / scale
                row[1] = (row[1] - oy) / scale
                row[2:4] /= scale
                row[4:14:2] = (row[4:14:2] - ox) / scale
                row[5:14:2] = (row[5:14:2] - oy) / scale
                cx, cy = (row[0] + row[2] / 2) / w, (row[1] + row[3] / 2) / h
                x1, y1, x2, y2 = c.driver_roi
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    roi_faces.append(row)
                    if min(row[2:4]) >= c.min_face_size:
                        candidates.append(row)
        # Size is measured in original camera pixels, not the padded detector input.
        largest = max(roi_faces, key=lambda row: min(row[2:4])) if roi_faces else None
        detection_metrics = {"detected_face_count": 0 if found is None else len(found),
                             "faces_in_driver_roi": len(roi_faces),
                             "accepted_face_count": len(candidates),
                             "min_face_size_threshold": c.min_face_size,
                             "face_min_side_pixels": None if largest is None else float(min(largest[2:4]))}
        if len(candidates) != 1:
            self.eye_motion.reset()
            if candidates:  # ambiguous drivers invalidate the old track
                self.previous_box = None
            quality = "ambiguous_faces" if candidates else "face_too_small" if roi_faces else "no_face"
            confidence = float(largest[-1]) if quality == "face_too_small" else None
            return VisionResult(quality, metrics=detection_metrics, confidence=confidence, eye_quality=quality)
        face = candidates[0]
        try:
            crops, boxes = face_crops(frame, face, c)
        except ValueError:
            self.eye_motion.reset()
            return VisionResult("invalid_landmarks", metrics=detection_metrics, confidence=float(face[-1]),
                                eye_quality="invalid_landmarks")
        changed = self.previous_box is None or iou(self.previous_box, boxes[2]) < 0.2
        self.previous_box = boxes[2]
        metrics = {**detection_metrics, **quality_metrics(crops[2])}
        eye_metrics = [quality_metrics(crop) for crop in crops[:2]]
        metrics["eye_brightness_min"] = min(m["brightness_median"] for m in eye_metrics)
        metrics["eye_sharpness_min"] = min(m["sharpness"] for m in eye_metrics)
        metrics["face_sharpness_threshold"] = c.min_sharpness
        metrics["eye_sharpness_threshold"] = c.min_eye_sharpness
        quality = assess_quality(metrics, c)
        if quality != "usable" or changed:
            self.eye_motion.reset()
        eye_quality, motion_metrics = self.eye_motion.update(face, timestamp) if quality == "usable" else (quality, {})
        metrics.update(motion_metrics)
        metrics["eye_quality"] = eye_quality
        return VisionResult(quality, crops, boxes, metrics, float(face[-1]), changed, eye_quality)
