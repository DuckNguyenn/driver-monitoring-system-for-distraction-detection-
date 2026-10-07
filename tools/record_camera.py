"""Record a short webcam clip plus exact software capture timestamps."""
import argparse
import json
from pathlib import Path
import platform
import time
import cv2

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=int, default=0)
parser.add_argument("--seconds", type=float, default=15)
parser.add_argument("--output", required=True)
args = parser.parse_args()
path = Path(args.output).resolve()
path.parent.mkdir(parents=True, exist_ok=True)
if path.exists():
    raise SystemExit("Output exists; choose a new recording filename")
capture = cv2.VideoCapture(args.source, cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY)
capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
writer = None
times = []
start = time.monotonic()
try:
    if not capture.isOpened():
        raise RuntimeError("camera unavailable")
    while time.monotonic() - start < args.seconds:
        ok, frame = capture.read()
        timestamp = time.monotonic()
        if not ok:
            raise RuntimeError("camera read failed")
        if writer is None:
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (frame.shape[1], frame.shape[0]))
            if not writer.isOpened():
                raise RuntimeError("video writer unavailable")
            origin = timestamp
        writer.write(frame)
        times.append(timestamp - origin)
finally:
    capture.release()
    if writer:
        writer.release()
    if times:
        metadata = {"source": args.source, "timestamps_seconds": times, "note": "Use sidecar timestamps, AVI header is nominal 30 FPS."}
        path.with_suffix(".timestamps.json").write_text(json.dumps(metadata), encoding="utf-8")
print(json.dumps({"video": str(path), "frames": len(times), "capture_seconds": times[-1] if times else 0}), flush=True)
