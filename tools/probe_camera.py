"""Report accessible camera indexes without a GUI or model downloads."""
import cv2
import json
import platform
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--indexes", type=int, nargs="+", default=[0, 1, 2, 3])
args = parser.parse_args()
for index in args.indexes:
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY)
    try:
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        print(json.dumps({"index": index, "opened": cap.isOpened(), "frame": list(frame.shape) if ok else None,
                          "fps": cap.get(cv2.CAP_PROP_FPS)}), flush=True)
    finally:
        cap.release()
