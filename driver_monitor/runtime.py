"""The shared camera/video execution loop."""
from dataclasses import asdict
from collections import Counter
import signal
import time
import math
import cv2
import numpy as np

from .alerting import NullAlertSink, SerialAlertSink
from .capture import Capture
from .core import Monitor, Observation
from .journal import Journal
from .models import Classifier, read_manifest, sha256
from .overlay import draw_overlay
from .vision import Vision, orient_frame


def run(config, source, duration=0.0):
    monitor = Monitor(config.monitor)
    classifiers = []
    capture = sink = journal = None
    stopped = False
    old_handlers = {}
    def stop(*_):
        nonlocal stopped
        stopped = True
    for name in (signal.SIGINT, signal.SIGTERM):
        old_handlers[name] = signal.signal(name, stop)
    latencies, processing, counters = Counter(), Counter(), Counter()
    def percentile(histogram):
        target = sum(histogram.values()) * .95
        count = 0
        for value in sorted(histogram):
            count += histogram[value]
            if count >= target:
                return value
        return None
    total, failure = 0, None
    began = time.monotonic()
    first_timestamp = last_timestamp = None
    try:
        # Startup failures must leave evidence even when a model or camera never opens.
        journal = Journal(config.log_dir, {"source": str(source), "config": asdict(config)}, event_name="startup")
        vision = Vision(config)
        eye = Classifier(config.manifest, "eye", config.backend, config.cpu_threads)
        classifiers.append(eye)
        yawn = Classifier(config.manifest, "yawn", config.backend, config.cpu_threads)
        classifiers.append(yawn)
        # Warm-up before opening capture, so startup cannot fabricate stale evidence.
        sample = np.zeros((224, 224, 3), np.uint8)
        eye.predict(sample)
        yawn.predict(sample)
        sink = SerialAlertSink(config.serial_port, config.serial_baud, freshness=config.monitor.max_frame_gap_seconds) if config.serial_port else NullAlertSink()
        capture = Capture(source, config.width, config.height)
        journal.event("session_start", **{"source": str(source), "live": capture.live, "backend": config.backend,
                                           "source_sha256": None if capture.live else sha256(source),
                                           "config": asdict(config), "config_sha256": config.fingerprint(),
                                           "eye_order": "driver_anatomical_left_right",
                                           "manifest": read_manifest(config.manifest)})
        print(f"Running {source} ({config.backend}); log: {journal.session}", flush=True)
        began = time.monotonic()
        while not stopped:
            if duration and time.monotonic() - began >= duration:
                break
            if config.max_frames and total >= config.max_frames:
                break
            packet = capture.read()
            if packet is None:
                sink.set_alert(False)
                if capture.eof:
                    break
                t = time.monotonic()
                status = monitor.update(Observation(t, quality=capture.error or "camera_timeout"))
                last_timestamp = t
                journal.event("camera_fault", **asdict(status))
                if capture.error:
                    raise RuntimeError(capture.error)
                continue
            if config.realtime and not capture.live:
                # Presentation speed never changes the source timestamps used by Monitor.
                while not stopped and time.monotonic() < began + packet.timestamp:
                    if duration and time.monotonic() - began >= duration:
                        stopped = True
                        break
                    time.sleep(min(.05, max(0, began + packet.timestamp - time.monotonic())))
                if stopped:
                    break
            start = time.monotonic()
            if capture.live and last_timestamp is not None and packet.timestamp <= last_timestamp:
                continue  # buffered frame predates an emitted timeout
            packet.image = orient_frame(packet.image, config.rotation_degrees)
            result = vision.observe(packet.image, timestamp=packet.timestamp)
            result.metrics.update(frame_width=int(packet.image.shape[1]), frame_height=int(packet.image.shape[0]))
            left = right = mouth = None
            if result.quality == "usable":
                left, right = (eye.predict(crop) for crop in result.crops[:2])
                mouth = yawn.predict(result.crops[2])
            decision = time.monotonic()
            age = decision - packet.acquired_at if capture.live else 0.0
            obs = Observation(packet.timestamp, left, right, mouth, result.quality, age, result.track_changed,
                              result.eye_quality)
            status = monitor.update(obs)
            sink.set_alert(status.alert, status.reasons)
            last_timestamp = packet.timestamp
            if first_timestamp is None:
                first_timestamp = packet.timestamp
            total += 1
            latency = (decision - packet.acquired_at) * 1000
            cost = (decision - start) * 1000
            latencies[min(5000, math.ceil(latency))] += 1
            processing[min(5000, math.ceil(cost))] += 1
            counters[status.state] += 1
            fps = total / max(decision - began, 1e-9)
            journal.record(obs, status, packet.index, latency, cost, decision, fps, sink.last_error, result.metrics)
            if not config.headless:
                displayed_time = packet.timestamp - first_timestamp if capture.live else packet.timestamp
                output = draw_overlay(packet.image, result, status, obs, config,
                                      elapsed=displayed_time, fps=fps, latency_ms=latency)
                cv2.imshow("Driver monitor", output)
                if cv2.waitKey(1) & 0xff in (ord("q"), 27):
                    break
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        if journal:
            journal.event("runtime_fault", error=failure, state="UNKNOWN", alert=False)
        raise
    finally:
        elapsed = time.monotonic() - began
        if sink:
            sink.set_alert(False)
            sink.close()
        if capture:
            capture.close()
        for classifier in classifiers:
            classifier.close()
        if not config.headless:
            cv2.destroyAllWindows()
        for name, handler in old_handlers.items():
            signal.signal(name, handler)
        if journal:
            summary = {"source": str(source), "live": capture.live if capture else None, "backend": config.backend,
                       "frames": total, "wall_seconds": elapsed,
                       "media_seconds": None if first_timestamp is None else last_timestamp - first_timestamp,
                       "fps": total / max(elapsed, 1e-9), "states": dict(counters),
                       "latency_p95_ms": percentile(latencies),
                       "processing_p95_ms": percentile(processing),
                       "percentile_resolution_ms": 1, "percentile_overflow_ms": 5000,
                       "fault": failure, "accuracy": None, "accuracy_note": "Ground truth required; throughput is not accuracy."}
            path = journal.close(summary)
            print(f"Summary: {path}", flush=True)
    return summary
