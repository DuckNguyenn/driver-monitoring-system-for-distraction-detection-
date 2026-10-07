"""Classical-vision ROI runtime for the eye/yawn classifiers.

Pipeline:
OpenCV Haar cascade (Viola-Jones: Haar-like + AdaBoost + cascade)
-> face ROI
-> MediaPipe Face Mesh landmarks
-> Euclidean EAR/MAR geometry
-> eye/yawn classification models
-> temporal yawn decision

The classifier checkpoints must be Ultralytics *classification* checkpoints.
They are not detection checkpoints and must not be used with .plot().
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

import cv2
import numpy as np
import os
_cache = Path(__file__).resolve().parent.parent / ".cache/ultralytics"
_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_cache))
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from .alerting import NullAlertSink, SerialAlertSink
    from .drowsiness import DrowsinessConfig, DrowsinessMonitor
except ImportError:  # direct ``python camera_classical.py`` execution
    from alerting import NullAlertSink, SerialAlertSink
    from drowsiness import DrowsinessConfig, DrowsinessMonitor

try:
    from mediapipe.python.solutions.face_mesh import FaceMesh
except ImportError as exc:
    raise SystemExit(
        "Không thể import Face Mesh. Hãy chạy: "
        "python -m pip install mediapipe"
    ) from exc

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
# The repository already bundles the trained classification checkpoints next
# to this runtime. CLI flags still allow swapping in calibrated checkpoints.
DEFAULT_EYE = HERE / "best_eye.pt"
DEFAULT_YAWN = HERE / "best_yawn.pt"

# MediaPipe Face Mesh indices. The ratios use Euclidean distances between
# landmarks, so they remain more stable than raw pixel distances.
LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)
MOUTH = (61, 291, 13, 14)


def euclidean(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def ear(points: np.ndarray, ids: tuple[int, ...]) -> float:
    p = points[list(ids)]
    horizontal = euclidean(p[0], p[3])
    if horizontal <= 1e-8:
        return 0.0
    return (euclidean(p[1], p[5]) + euclidean(p[2], p[4])) / (2.0 * horizontal)


def mar(points: np.ndarray) -> float:
    p = points[list(MOUTH)]
    width = euclidean(p[0], p[1])
    if width <= 1e-8:
        return 0.0
    return euclidean(p[2], p[3]) / width


def clamp_box(x: int, y: int, w: int, h: int, shape: tuple[int, ...]):
    height, width = shape[:2]
    x1 = max(0, min(width - 1, x))
    y1 = max(0, min(height - 1, y))
    x2 = max(x1 + 1, min(width, x + w))
    y2 = max(y1 + 1, min(height, y + h))
    return x1, y1, x2, y2


def crop_from_points(frame: np.ndarray, points: np.ndarray, ids, pad_x: float, pad_y: float):
    p = points[list(ids)]
    x_min, y_min = p.min(axis=0)
    x_max, y_max = p.max(axis=0)
    w = max(2.0, x_max - x_min)
    h = max(2.0, y_max - y_min)
    box = clamp_box(
        int(x_min - pad_x * w), int(y_min - pad_y * h),
        int(w * (1 + 2 * pad_x)), int(h * (1 + 2 * pad_y)), frame.shape,
    )
    x1, y1, x2, y2 = box
    return frame[y1:y2, x1:x2].copy(), box


def face_mesh_points(frame: np.ndarray, face_box, mesh):
    x1, y1, x2, y2 = face_box
    face = frame[y1:y2, x1:x2]
    if face.size == 0:
        return None
    rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
    result = mesh.process(rgb)
    if not result.multi_face_landmarks:
        return None
    fh, fw = face.shape[:2]
    points = np.array(
        [[lm.x * fw + x1, lm.y * fh + y1] for lm in result.multi_face_landmarks[0].landmark],
        dtype=np.float32,
    )
    return points


def choose_face(faces, frame_shape):
    if len(faces) == 0:
        return None
    # Prefer the largest detected face near the upper/central image area.
    h, w = frame_shape[:2]
    candidates = []
    for x, y, fw, fh in faces:
        area = fw * fh
        center_penalty = abs((x + fw / 2) - w / 2) / max(w, 1)
        upper_penalty = max(0.0, (y - h * 0.55) / max(h, 1))
        candidates.append((area - area * 0.25 * center_penalty - area * 0.25 * upper_penalty, (x, y, fw, fh)))
    x, y, fw, fh = max(candidates, key=lambda item: item[0])[1]
    # Add a little margin so Face Mesh sees the complete face.
    return clamp_box(int(x - 0.12 * fw), int(y - 0.16 * fh), int(fw * 1.24), int(fh * 1.28), frame_shape)


def classify(model, crop: np.ndarray):
    if crop is None or crop.size == 0:
        return None, 0.0, None
    result = model.predict(source=crop, imgsz=224, verbose=False)[0]
    probs = result.probs
    if probs is None:
        return None, 0.0, None
    index = int(probs.top1)
    confidence = float(probs.top1conf)
    names = model.names
    label = names[index] if isinstance(names, dict) else names[index]
    all_probs = probs.data.detach().cpu().numpy().astype(float) if hasattr(probs.data, "detach") else np.asarray(probs.data, dtype=float)
    return str(label), confidence, all_probs


def main():
    parser = argparse.ArgumentParser(description="Haar + Face Mesh + Euclidean + classification camera")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--eye-model", default=str(DEFAULT_EYE))
    parser.add_argument("--yawn-model", default=str(DEFAULT_YAWN))
    parser.add_argument("--ear-threshold", type=float, default=0.20)
    parser.add_argument("--mar-threshold", type=float, default=0.60)
    parser.add_argument("--face-scale", type=float, default=1.10)
    parser.add_argument("--esp32-port", default=None, help="Serial port for ESP32 buzzer, e.g. COM7 or /dev/ttyUSB0")
    parser.add_argument("--esp32-baud", type=int, default=115200)
    parser.add_argument("--eye-closed-seconds", type=float, default=1.5)
    parser.add_argument("--blink-min-count", type=int, default=4)
    parser.add_argument("--yawn-min-count", type=int, default=2)
    parser.add_argument("--yawn-window-seconds", type=float, default=60.0)
    args = parser.parse_args()

    if not Path(args.eye_model).exists():
        raise FileNotFoundError(f"Không thấy eye classification checkpoint: {args.eye_model}")
    if not Path(args.yawn_model).exists():
        raise FileNotFoundError(f"Không thấy yawn classification checkpoint: {args.yawn_model}")

    eye_model = YOLO(args.eye_model)
    yawn_model = YOLO(args.yawn_model)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_detector = cv2.CascadeClassifier(cascade_path)
    if face_detector.empty():
        raise RuntimeError(f"Không tải được Haar cascade: {cascade_path}")

    mesh = FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)
    monitor = DrowsinessMonitor(DrowsinessConfig(
        eye_closed_seconds=args.eye_closed_seconds,
        blink_min_count=args.blink_min_count,
        yawn_min_count=args.yawn_min_count,
        yawn_window_seconds=args.yawn_window_seconds,
    ))
    alert_sink = SerialAlertSink(args.esp32_port, args.esp32_baud) if args.esp32_port else NullAlertSink()
    camera = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not camera.isOpened():
        raise RuntimeError(f"Không mở được camera {args.camera}. Thử --camera 0 hoặc --camera 1.")

    print("Pipeline: Haar/AdaBoost -> Face Mesh -> Euclidean EAR/MAR -> classifiers -> temporal yawn")
    print("Nhấn Q hoặc ESC để thoát.")
    last_time = time.perf_counter()
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_detector.detectMultiScale(
                gray, scaleFactor=args.face_scale, minNeighbors=5, minSize=(80, 80)
            )
            face_box = choose_face(faces, frame.shape)
            output = frame.copy()
            eye_text = "eye: no face"
            yawn_text = "yawn: no face"
            if face_box is not None:
                x1, y1, x2, y2 = face_box
                cv2.rectangle(output, (x1, y1), (x2, y2), (255, 180, 0), 2)
                points = face_mesh_points(frame, face_box, mesh)
                if points is not None:
                    left_crop, left_box = crop_from_points(frame, points, (33, 160, 158, 133, 153, 144), 1.2, 1.2)
                    right_crop, right_box = crop_from_points(frame, points, (362, 385, 387, 263, 373, 380), 1.2, 1.2)
                    face_crop = frame[y1:y2, x1:x2]
                    left_label, left_conf, _ = classify(eye_model, left_crop)
                    right_label, right_conf, _ = classify(eye_model, right_crop)
                    yawn_label, yawn_conf, yawn_probs = classify(yawn_model, face_crop)
                    # Read the probability by class name, not by assumed index.
                    yawn_prob = 0.0
                    if yawn_probs is not None:
                        names = yawn_model.names
                        for idx, name in (names.items() if isinstance(names, dict) else enumerate(names)):
                            if str(name).lower() == "yawn":
                                yawn_prob = float(yawn_probs[idx])
                                break
                    now = time.perf_counter()
                    left_ear = ear(points, LEFT_EYE)
                    right_ear = ear(points, RIGHT_EYE)
                    mean_ear = (left_ear + right_ear) / 2.0
                    mouth_ratio = mar(points)
                    for bx in (left_box, right_box):
                        a, b, c, d = bx
                        cv2.rectangle(output, (a, b), (c, d), (80, 220, 80), 2)
                    # Geometry is an interpretable signal and sanity check. It does not
                    # overwrite the classifier label automatically.
                    eye_text = f"L:{left_label} {left_conf:.2f}  R:{right_label} {right_conf:.2f}  EAR:{mean_ear:.2f}"
                    closed_labels = (
                        str(left_label).lower() == "closed"
                        and str(right_label).lower() == "closed"
                    )
                    open_labels = str(left_label).lower() == "open" and str(right_label).lower() == "open"
                    eye_closed = closed_labels if min(left_conf, right_conf) >= 0.8 and (closed_labels or open_labels) else None
                    status = monitor.update(now, eye_closed, yawn_prob)
                    yawn_text = f"{status.yawn_state}  P:{yawn_prob:.2f}  yawns:{status.yawn_count}  MAR:{mouth_ratio:.2f}"
                    if mean_ear < args.ear_threshold:
                        eye_text += "  [geometry: closed]"
                    if mouth_ratio > args.mar_threshold:
                        yawn_text += "  [geometry: open]"
                    alert_sink.set_alert(status.alert, status.reasons)
                    if status.alert:
                        cv2.putText(output, "DROWSINESS ALERT: " + ",".join(status.reasons), (12, 103), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
                else:
                    # A missing landmark result is equivalent to a missing face;
                    # never keep the buzzer latched on stale evidence.
                    monitor.update(time.perf_counter(), None, None)
                    alert_sink.set_alert(False)
            else:
                status = monitor.update(time.perf_counter(), None, None)
                alert_sink.set_alert(False)

            cv2.putText(output, eye_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            cv2.putText(output, yawn_text, (12, 53), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            now = time.perf_counter()
            fps = 1.0 / max(now - last_time, 1e-6)
            last_time = now
            cv2.putText(output, f"FPS:{fps:.1f}", (12, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            cv2.imshow("Classical eye/yawn camera", output)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        camera.release()
        if hasattr(alert_sink, "close"):
            alert_sink.close()
        mesh.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
