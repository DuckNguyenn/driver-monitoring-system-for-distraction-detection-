"""Latest-frame camera capture; sequential video uses media timestamps."""
from dataclasses import dataclass
from pathlib import Path
import platform
import queue
import threading
import time
import cv2
import json
from math import isfinite


@dataclass
class Frame:
    timestamp: float
    image: object
    acquired_at: float
    index: int


class Capture:
    def __init__(self, source, width=640, height=480):
        self.live = str(source).isdigit() or str(source).startswith("/dev/video")
        source = int(source) if str(source).isdigit() else str(source)
        backend = cv2.CAP_DSHOW if self.live and platform.system() == "Windows" else cv2.CAP_V4L2 if self.live and platform.system() == "Linux" else cv2.CAP_ANY
        self.capture = cv2.VideoCapture(source, backend)
        if not self.capture.isOpened():
            self.capture.release()
            raise RuntimeError(f"Cannot open camera/video: {source}")
        if self.live:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        if not self.live and (not 0 < self.fps < 1000):
            self.capture.release()
            raise ValueError("video has no valid FPS/timestamp metadata")
        self.index = 0
        self.error = None
        self.eof = False
        self._stop = threading.Event()
        self._queue = queue.Queue(maxsize=1)
        self._thread = None
        self._last_pts = -1.0
        self._pts = None
        if not self.live:
            sidecar = Path(source).with_suffix(".timestamps.json")
            if sidecar.is_file():
                try:
                    self._pts = json.loads(sidecar.read_text(encoding="utf-8"))["timestamps_seconds"]
                    if not self._pts or any(not isfinite(t) or t < 0 for t in self._pts) or any(a >= b for a, b in zip(self._pts, self._pts[1:])):
                        raise ValueError("invalid recording timestamps")
                except (ValueError, TypeError, KeyError):
                    self.capture.release()
                    raise ValueError("invalid recording timestamps") from None
        if self.live:
            self._thread = threading.Thread(target=self._produce, name="camera-latest", daemon=True)
            self._thread.start()

    def _produce(self):
        try:
            while not self._stop.is_set():
                ok, image = self.capture.read()
                acquired = time.monotonic()
                if not ok:
                    self.error = "camera_read_failed"
                    break
                packet = Frame(acquired, image, acquired, self.index)
                self.index += 1
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._queue.put_nowait(packet)
                except queue.Full:
                    pass
        except Exception as exc:
            self.error = f"camera_exception: {exc}"
        finally:
            self.capture.release()

    def read(self, timeout=0.15):
        if self.live:
            try:
                return self._queue.get(timeout=timeout)
            except queue.Empty:
                return None
        ok, image = self.capture.read()
        acquired = time.monotonic()
        if not ok:
            if self._pts is not None and self.index != len(self._pts):
                raise ValueError("recording timestamp count does not match decoded frames")
            self.eof = True
            return None
        pts = self.capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if not isfinite(pts) or pts < 0:
            pts = self.index / self.fps
        if self._pts is not None:
            if self.index >= len(self._pts):
                raise ValueError("recording has fewer timestamps than frames")
            pts = self._pts[self.index]
        if self.index == 0:
            self._origin_pts = pts
        pts -= self._origin_pts
        if pts <= self._last_pts:
            pts = self.index / self.fps  # codecs which do not expose PTS
        if pts <= self._last_pts:
            raise ValueError("nonmonotonic video timestamps")
        self._last_pts = pts
        packet = Frame(pts, image, acquired, self.index)
        self.index += 1
        return packet

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        else:
            self.capture.release()
