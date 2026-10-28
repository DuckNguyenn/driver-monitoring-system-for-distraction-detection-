"""Nonblocking worker-side telemetry, independent of the monitor's decisions."""
import queue
import time

from .dashboard_data import snapshot, utc_now
from .dashboard_video import PreviewEncoder


def offer_latest(channel, value):
    """Bounded channels may discard telemetry, never stall the camera."""
    try:
        channel.put_nowait(value)
        return
    except queue.Full:
        pass
    try:
        channel.get_nowait()
    except queue.Empty:
        return  # multiprocessing's feeder has not exposed the old item yet
    try:
        channel.put_nowait(value)
    except queue.Full:
        pass


class DashboardPublisher:
    def __init__(self, statuses, frames, preview_demand, status_interval=.2, preview_fps=15, clock=time.monotonic):
        self.statuses, self.frames, self.demand = statuses, frames, preview_demand
        self.interval = status_interval
        self.clock = clock
        self.session, self.metadata, self.sequence = "", {}, 0
        self.last_sent = 0.
        self.last_state, self.alert_active, self.episode = None, False, 0
        self.frame_sequence = 0
        self.encoder = PreviewEncoder(frames, preview_demand, preview_fps, clock)

    def wants_preview(self):
        return self.demand.value > self.clock() and not self.encoder.stopped.is_set()

    def start(self, session, metadata):
        self.session, self.metadata = session, metadata
        self._publish({"utc": utc_now()}, "initializing")

    def _publish(self, record, lifecycle="running"):
        self.sequence += 1
        record = dict(record, alert_episode_id=f"{self.session}:{self.episode}" if self.alert_active else None)
        offer_latest(self.statuses, dict(snapshot(record, self.session, self.sequence, self.metadata, lifecycle), _published_at=self.clock()))

    def record(self, record, frame=None, boxes=()):
        now = self.clock()
        alert = bool(record.get("alert"))
        if alert and not self.alert_active:
            self.episode += 1
        changed = self.last_state != (record.get("state"), alert, tuple(record.get("reasons") or []))
        self.alert_active = alert
        self.last_state = (record.get("state"), alert, tuple(record.get("reasons") or []))
        if changed or now - self.last_sent >= self.interval:
            self._publish(record)
            self.last_sent = now
        if frame is None or not self.wants_preview():
            return
        self.frame_sequence += 1
        self.encoder.offer(frame, self.frame_sequence, record.get("_frame_acquired_at", now), boxes)

    def close(self):
        self.encoder.close()

    def fault(self, error):
        self.alert_active = False
        self._publish({"error": str(error), "reasons": ["runtime_fault"]}, "error")

    def end(self, summary):
        self.close()
        self.alert_active = False
        self._publish({"fault": summary.get("fault"), "reasons": ["runtime_fault"] if summary.get("fault") else []},
                      "error" if summary.get("fault") else "finished")
