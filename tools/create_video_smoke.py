"""Technical video fixture from still images; never temporal accuracy evidence."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import cv2
from driver_monitor.config import Config, ROOT
from driver_monitor.models import Classifier
from driver_monitor.vision import Vision

config = Config()
vision = Vision(config)
eye = Classifier(config.manifest, "eye", "onnx")
yawn = Classifier(config.manifest, "yawn", "onnx")
chosen = []
try:
    for label in ("no_yawn", "yawn"):
        for path in sorted((ROOT / "kaggle_output/data/yawn_dataset/images/test").glob(f"{label}*.jpg")):
            image = cv2.imread(str(path))
            if image.shape[:2] != (480, 640):
                image = cv2.resize(image, (640, 480))
            found = vision.observe(image)
            if found.quality != "usable":
                continue
            left, right = [eye.predict(crop) for crop in found.crops[:2]]
            p = yawn.predict(found.crops[2])["yawn"]
            if min(left["Open"], right["Open"]) >= .8 and (p <= .35 if label == "no_yawn" else p >= .7):
                chosen.append((image, str(path), label, p))
                break
    if len(chosen) != 2:
        raise RuntimeError("no suitable positive/negative video fixture images")
    output = ROOT / "reports/video_fixture.avi"
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"MJPG"), 15, (640, 480))
    if not writer.isOpened():
        raise RuntimeError("video writer unavailable")
    try:
        for index in (0, 1, 0):
            for _ in range(45):
                writer.write(chosen[index][0])
    finally:
        writer.release()
    output.with_suffix(".fixture.json").write_text(json.dumps({"purpose": "decoder + real classifier + time-state regression ONLY; still-image repetition is not a real yawn video", "fps": 15,
               "sources": [{"file": path, "label": label, "yawn_probability": p} for _, path, label, p in chosen]}, indent=2), encoding="utf-8")
    print(output)
finally:
    eye.close()
    yawn.close()
