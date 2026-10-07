"""Explicit model download with Git LFS SHA-256 verification."""
import json
from pathlib import Path
import urllib.request
from .models import sha256

YUNET_NAME = "face_detection_yunet_2023mar.onnx"
SOURCE = "https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet"


def fetch_yunet(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request("https://api.github.com/repos/opencv/opencv_zoo/commits/main", headers={"User-Agent": "driver-monitor"})
    with urllib.request.urlopen(request, timeout=30) as response:
        commit = json.load(response)["sha"]
    relative = f"models/face_detection_yunet/{YUNET_NAME}"
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/opencv/opencv_zoo/{commit}/{relative}", timeout=30) as response:
        pointer = response.read().decode("utf-8")
    expected = next(line.split("sha256:")[1] for line in pointer.splitlines() if line.startswith("oid sha256:"))
    path = directory / YUNET_NAME
    if not path.exists() or sha256(path) != expected:
        with urllib.request.urlopen(f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{commit}/{relative}", timeout=60) as response:
            data = response.read()
        import hashlib
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("YuNet Git LFS checksum mismatch")
        temporary = path.with_suffix(".download")
        temporary.write_bytes(data)
        temporary.replace(path)
    record = {"file": path.name, "sha256": expected, "source": SOURCE, "commit": commit, "license": "MIT", "input_size": 320}
    (directory / "yunet.source.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record
