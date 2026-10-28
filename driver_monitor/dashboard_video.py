"""Encode the latest rendered monitor view off the inference thread."""
import logging
import queue
import threading
import time


class PreviewEncoder:
    def __init__(self, frames, demand, fps=15, clock=time.monotonic):
        self.frames, self.demand, self.clock = frames, demand, clock
        self.interval = 1 / fps
        self.pending = queue.Queue(1)
        self.stopped = threading.Event()
        self.thread = None
        self.last_error = None

    def offer(self, frame, sequence, captured_at, boxes=()):
        from .dashboard_transport import offer_latest
        if self.stopped.is_set() or self.demand.value <= self.clock():
            return
        # Own the pixels; camera/display callers may release their frame immediately.
        offer_latest(self.pending, (frame.copy(), sequence, captured_at, tuple(boxes)))
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, name="dashboard-jpeg", daemon=True)
            self.thread.start()

    def _run(self):
        import cv2
        from .dashboard_transport import offer_latest
        next_due = 0.
        while not self.stopped.wait(max(0., next_due - self.clock())):
            try:
                frame, sequence, captured_at, boxes = self.pending.get(timeout=.1)
            except queue.Empty:
                continue
            began = self.clock()
            next_due = began + self.interval
            if self.demand.value <= began or began - captured_at > 2:
                continue
            try:
                for x1, y1, x2, y2 in boxes:
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (50, 220, 70), 2)
                height, width = frame.shape[:2]
                scale = min(640 / width, 480 / height, 1.)
                if scale < 1:
                    frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
                if not ok:
                    raise RuntimeError("JPEG encoder returned no image")
                if not self.stopped.is_set():
                    offer_latest(self.frames, {"jpeg": encoded.tobytes(), "sequence": sequence,
                                              "time": captured_at, "encoded_at": self.clock()})
                self.last_error = None
            except Exception as exc:
                error = type(exc).__name__
                if self.last_error != error:
                    logging.getLogger(__name__).warning("Dashboard JPEG encoding failed: %s", error)
                self.last_error = error

    def close(self):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join(timeout=2.)
