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
from .eyewear import EyeRouter, read_eyewear_manifest


def run(config, source, duration=0.0, observer=None, stop_event=None):
    monitor = Monitor(config.monitor)
    classifiers = []
    capture = sink = journal = router = None
    stopped = False
    old_handlers = {}
    def publish(method, *args):
        nonlocal observer
        if observer is None:
            return
        try:
            return getattr(observer, method)(*args)
        except Exception as exc:
            # Telemetry is optional: device/monitor decisions must keep running.
            observer = None
            if journal:
                journal.event("telemetry_fault", error=f"{type(exc).__name__}: {exc}")
    def stopping():
        return stopped or (stop_event is not None and stop_event.is_set())
    def stop(*_):
        nonlocal stopped
        stopped = True
    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        signals.append(signal.SIGBREAK)
    for name in signals:
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
        publish("start", journal.session, {"source": str(source), "config": asdict(config), "backend": config.backend})
        vision = Vision(config)
        eye = Classifier(config.manifest, "eye", config.backend, config.cpu_threads)
        classifiers.append(eye)
        yawn = Classifier(config.manifest, "yawn", config.backend, config.cpu_threads)
        classifiers.append(yawn)
        if config.auto_glasses:
            router = EyeRouter(eye, config)
            classifiers.append(router)
        # Warm-up before opening capture, so startup cannot fabricate stale evidence.
        sample = np.zeros((224, 224, 3), np.uint8)
        eye.predict(sample)
        yawn.predict(sample)
        if router:
            router.warmup(sample)
            journal.event("eye_routing_enabled", selector=read_eyewear_manifest(config.eyewear_manifest),
                          specialist=read_manifest(config.glasses_eye_manifest)["classifiers"]["eye"],
                          original=read_manifest(config.manifest)["classifiers"]["eye"],
                          yawn_model_preserved=True)
        sink = SerialAlertSink(config.serial_port, config.serial_baud, freshness=config.monitor.max_frame_gap_seconds) if config.serial_port else NullAlertSink()
        capture = Capture(source, config.width, config.height)
        journal.event("session_start", **{"source": str(source), "live": capture.live, "backend": config.backend,
                                           "source_sha256": None if capture.live else sha256(source),
                                           "config": asdict(config), "config_sha256": config.fingerprint(),
                                           "eye_order": "driver_anatomical_left_right",
                                           "manifest": read_manifest(config.manifest)})
        publish("start", journal.session, {"source": str(source), "live": capture.live, "backend": config.backend, "config": asdict(config)})
        print(f"Running {source} ({config.backend}); log: {journal.session}", flush=True)
        began = time.monotonic()
        while not stopping():
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
                missing = Observation(t, quality=capture.error or "camera_timeout")
                status = monitor.update(missing)
                if router:
                    router.gate.reset()
                last_timestamp = t
                journal.event("camera_fault", **asdict(status))
                publish("record", {**asdict(status), "observation": asdict(missing), "error": capture.error})
                if capture.error:
                    raise RuntimeError(capture.error)
                continue
            if config.realtime and not capture.live:
                # Presentation speed never changes the source timestamps used by Monitor.
                while not stopping() and time.monotonic() < began + packet.timestamp:
                    if duration and time.monotonic() - began >= duration:
                        stopped = True
                        break
                    time.sleep(min(.05, max(0, began + packet.timestamp - time.monotonic())))
                if stopping():
                    break
            start = time.monotonic()
            if capture.live and last_timestamp is not None and packet.timestamp <= last_timestamp:
                continue  # buffered frame predates an emitted timeout
            packet.image = orient_frame(packet.image, config.rotation_degrees)
            result = vision.observe(packet.image, timestamp=packet.timestamp)
            result.metrics.update(frame_width=int(packet.image.shape[1]), frame_height=int(packet.image.shape[0]))
            left = right = mouth = None
            selected_eye = eye
            if router:
                previous_error = router.error
                selected_eye, route = router.select(result, packet.timestamp)
                if router.error and router.error != previous_error:
                    journal.event("eyewear_fault", timestamp=packet.timestamp, error=router.error,
                                  fallback="original_eye", yawn_model_preserved=True)
                if route.changed:
                    journal.event("eye_model_changed", timestamp=packet.timestamp, branch=route.branch,
                                  eyewear_probability=route.probability, error=router.error)
            if result.quality == "usable":
                left, right = (selected_eye.predict(crop) for crop in result.crops[:2])
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
            output = None
            wants_preview = observer is not None and (not hasattr(observer, "wants_preview") or publish("wants_preview"))
            if not config.headless or wants_preview:
                displayed_time = packet.timestamp - first_timestamp if capture.live else packet.timestamp
                output = draw_overlay(packet.image, result, status, obs, config,
                                      elapsed=displayed_time, fps=fps, latency_ms=latency)
            if observer is not None:
                ack = getattr(sink, "last_ack", None)
                publish("record", {**asdict(status), "observation": asdict(obs), "fps": fps, "latency_ms": latency,
                        "_frame_acquired_at": packet.acquired_at,
                        "processing_ms": cost, "serial_error": sink.last_error, "quality_metrics": result.metrics,
                        "serial_ack_age_seconds": None if ack is None else max(0., decision - ack)}, output, ())
            if not config.headless:
                cv2.imshow("Driver monitor", output)
                if cv2.waitKey(1) & 0xff in (ord("q"), 27):
                    break
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        if journal:
            journal.event("runtime_fault", error=failure, state="UNKNOWN", alert=False)
        publish("fault", failure)
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
            publish("end", summary)
            print(f"Summary: {path}", flush=True)
    return summary
