"""Versioned, nullable telemetry shared by the LAN clients and history index."""
from datetime import datetime, timezone
import math


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def finite(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except OverflowError:
        return None


def closed(values):
    if not isinstance(values, dict):
        return None
    return finite(next((v for k, v in values.items() if isinstance(k, str) and k.casefold() == "closed"), None))


def count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def normalize_record(record):
    """Normalize only derived telemetry; original JSONL bytes remain untouched."""
    if not isinstance(record, dict) or not isinstance(record.get("event", "unknown"), str):
        raise ValueError("Invalid JSONL event")
    record = dict(record)
    record["event"] = record.get("event", "unknown")
    for key in ("utc", "error", "fault", "serial_error", "backend"):
        if key in record and not isinstance(record[key], str):
            record[key] = None
    if record.get("state") not in ("NORMAL", "WARNING", "ALERT", "UNKNOWN"):
        record["state"] = "UNKNOWN"
    record["alert"] = record.get("alert") is True
    reasons = record.get("reasons")
    record["reasons"] = [reasons] if isinstance(reasons, str) else [v for v in reasons if isinstance(v, str)] if isinstance(reasons, (list, tuple)) else []
    record["config"] = record.get("config") if isinstance(record.get("config"), dict) else {}
    for key in ("frames", "blink_total", "blink_count", "yawn_count", "left_eye_events", "right_eye_events"):
        if key in record:
            record[key] = count(record[key])
    for key in ("timestamp", "fps", "latency_ms", "latency_p95_ms", "processing_ms", "serial_ack_age_seconds", "yawn_probability", "yawn_raw_probability"):
        if key in record:
            record[key] = finite(record[key])
    observation = record.get("observation")
    observation = dict(observation) if isinstance(observation, dict) else {}
    for key in ("quality", "eye_quality"):
        if not isinstance(observation.get(key), str):
            observation[key] = None
    record["observation"] = observation
    metrics = record.get("quality_metrics")
    record["quality_metrics"] = {k: v if isinstance(v, str) else finite(v) for k, v in metrics.items()} if isinstance(metrics, dict) else {}
    return record


def snapshot(record, session_id, sequence, metadata=None, lifecycle="running"):
    record = normalize_record(record)
    metadata = metadata if isinstance(metadata, dict) else {}
    observation = record.get("observation")
    observation = observation if isinstance(observation, dict) else {}
    config = metadata.get("config")
    configured = bool(config.get("serial_port")) if isinstance(config, dict) else False
    serial_error = record.get("serial_error")
    ack_age = finite(record.get("serial_ack_age_seconds"))
    esp32_state = ("not_configured" if not configured else "error" if serial_error else
                   "connected" if ack_age is not None and 0 <= ack_age <= 2 else "unconfirmed")
    quality = observation.get("quality") or "unavailable"
    left_events, right_events = count(record.get("left_eye_events")), count(record.get("right_eye_events"))
    fault = record.get("error") or record.get("fault")
    state = record.get("state", "UNKNOWN") if lifecycle == "running" else "UNKNOWN"
    return {
        "schema_version": 1, "session_id": session_id, "sequence": sequence,
        "utc": record.get("utc") or utc_now(), "source_timestamp": finite(record.get("timestamp")),
        "source_kind": "camera" if metadata.get("live") is True else "video" if metadata.get("live") is False else "unknown",
        "source": str(metadata.get("source", "")), "backend": metadata.get("backend"), "lifecycle": lifecycle,
        "state": state, "alert": bool(record.get("alert")) if lifecycle == "running" else False,
        "alert_episode_id": record.get("alert_episode_id"), "reasons": list(record.get("reasons") or []),
        "probabilities": {"eye_1_closed": closed(observation.get("left_eye")),
                          "eye_2_closed": closed(observation.get("right_eye")),
                          "yawn": finite(record.get("yawn_probability")), "yawn_raw": finite(record.get("yawn_raw_probability"))},
        "counts": {"blink_total": count(record.get("blink_total")), "blink_5s": count(record.get("blink_count")),
                   "yawn_60s": count(record.get("yawn_count")),
                   "eye_cycles": None if left_events is None or right_events is None else left_events + right_events},
        "quality": {"image": quality, "eyes": observation.get("eye_quality") or "unavailable", "metrics": record.get("quality_metrics") or {}},
        "performance": {"fps": finite(record.get("fps")), "latency_ms": finite(record.get("latency_ms")),
                        "processing_ms": finite(record.get("processing_ms"))},
        "devices": {"camera": {"state": "error" if fault or quality.startswith("camera_") else "connected" if lifecycle == "running" else "inactive", "error": fault},
                    "models": {"state": "ready" if lifecycle == "running" else "error" if fault else "inactive", "error": fault},
                    "esp32": {"state": esp32_state, "configured": configured, "error": serial_error, "ack_age_seconds": ack_age}},
        "connected": lifecycle == "running", "age_ms": 0.0,
    }
