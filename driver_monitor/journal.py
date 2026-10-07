"""Per-frame evidence plus one-second status records, never inferred accuracy."""
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import time
import glob


def telemetry():
    result = {}
    try:
        import psutil
        process = psutil.Process()
        result["rss_bytes"] = process.memory_info().rss
        result["cpu_times_seconds"] = sum(process.cpu_times()[:2])
        result["system_cpu_percent"] = psutil.cpu_percent()
    except ImportError:
        result["rss_bytes"] = None
    temps = {}
    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            temps[str(Path(path).parent.name)] = float(Path(path).read_text().strip()) / 1000
        except (OSError, ValueError):
            pass
    result["temperatures_c"] = temps
    try:
        result["npu_load"] = Path("/sys/kernel/debug/rknpu/load").read_text().strip()
    except OSError:
        result["npu_load"] = None
    return result


class Journal:
    def __init__(self, directory, metadata, event_name="session_start"):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.session = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        self.directory = directory
        self.events = (directory / f"{self.session}.jsonl").open("w", encoding="utf-8")
        self.frames = (directory / f"{self.session}.csv").open("w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.frames, fieldnames=["frame", "timestamp", "state", "alert", "reasons", "quality", "eye_quality", "eye_roll_degrees", "eye_motion_shift_ratio", "eye_motion_shape_ratio", "eye_motion_scale_ratio", "eye_motion_roll_change_degrees", "eye_motion_settle_remaining_seconds", "eye_closed", "left_closed", "right_closed", "yawn_probability", "yawn_raw_probability", "yawn_state", "yawn_count", "yawn_candidate_seconds", "blink_count", "blink_total", "blink_detected", "left_eye_events", "right_eye_events", "latency_ms", "processing_ms", "wall_timestamp", "serial_error"])
        self.writer.writeheader()
        self.last_state = None
        self.last_summary = float("-inf")
        self.event(event_name, **metadata)

    def event(self, kind, **values):
        self.events.write(json.dumps({"event": kind, "utc": datetime.now(timezone.utc).isoformat(), **values}, ensure_ascii=False, allow_nan=False, default=str) + "\n")
        self.events.flush()

    def record(self, observation, status, frame_index, latency_ms, processing_ms, wall_timestamp, fps, serial_error, metrics):
        def closed(values):
            if values is None:
                return ""
            return next((v for k, v in values.items() if k.casefold() == "closed"), "")
        self.writer.writerow(dict(frame=frame_index, timestamp=status.timestamp, state=status.state, alert=int(status.alert),
                                  reasons=",".join(status.reasons), quality=observation.quality, eye_quality=observation.eye_quality,
                                  **{name: metrics.get(name, "") for name in ("eye_roll_degrees", "eye_motion_shift_ratio", "eye_motion_shape_ratio", "eye_motion_scale_ratio", "eye_motion_roll_change_degrees", "eye_motion_settle_remaining_seconds")},
                                  eye_closed="" if status.eye_closed is None else int(status.eye_closed),
                                  left_closed=closed(observation.left_eye), right_closed=closed(observation.right_eye),
                                  yawn_probability=status.yawn_probability, yawn_raw_probability=status.yawn_raw_probability,
                                  yawn_state=status.yawn_state, yawn_count=status.yawn_count, yawn_candidate_seconds=status.yawn_candidate_seconds,
                                  blink_count=status.blink_count, blink_total=status.blink_total, blink_detected=int(status.blink_detected),
                                  left_eye_events=status.left_eye_events, right_eye_events=status.right_eye_events,
                                  latency_ms=latency_ms, processing_ms=processing_ms,
                                  wall_timestamp=wall_timestamp, serial_error=serial_error or ""))
        self.frames.flush()
        key = (status.state, status.reasons, serial_error, status.blink_total, status.left_eye_events,
               status.right_eye_events, status.yawn_state, status.yawn_count)
        if key != self.last_state or status.timestamp - self.last_summary >= 1:
            self.event("status", **asdict(status), observation=asdict(observation), fps=fps,
                       latency_ms=latency_ms, processing_ms=processing_ms, serial_error=serial_error,
                       quality_metrics=metrics, telemetry=telemetry())
            self.last_state, self.last_summary = key, status.timestamp

    def close(self, summary):
        self.event("session_end", **summary)
        self.events.close()
        self.frames.close()
        path = self.directory / f"{self.session}.summary.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        return path
