"""Camera overlay with eye probabilities and raw/filtered diagnostics."""
import cv2
import numpy as np

from .core import probabilities


def eye_label(values, threshold):
    values = probabilities(values, ("Closed", "Open"))
    if values is None:
        return "unknown", "?"
    state = "closed" if values["closed"] >= threshold else "open" if values["open"] >= threshold else "unknown"
    return state, f"{values['closed']:.2f}"


def draw_overlay(frame, vision, status, observation, config, *, elapsed, fps, latency_ms):
    output = frame.copy()
    height = output.shape[0]
    for panel in (output[:min(80, height)], output[max(0, height - 110):]):
        panel[:] = cv2.addWeighted(panel, .25, np.zeros_like(panel), .75, 0)
    def line(text, y, color=(0, 220, 220), scale=.48):
        cv2.putText(output, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)
    for x1, y1, x2, y2 in vision.boxes:
        cv2.rectangle(output, (x1, y1), (x2, y2), (80, 220, 80), 2)
    left = eye_label(observation.left_eye, config.monitor.eye_confidence)
    right = eye_label(observation.right_eye, config.monitor.eye_confidence)
    line(f"{status.state}: {','.join(status.reasons)}", 23, (0, 0, 255) if status.alert else (0, 220, 220), .55)
    line(f"t:{elapsed:.2f}s | {fps:.1f} FPS | {latency_ms:.1f} ms | yawns:{status.yawn_count}", 47)
    eyes = "unknown" if status.eye_closed is None else "both closed" if status.eye_closed else "both open"
    if (observation.quality == "usable" and observation.eye_quality == "usable"
            and {left[0], right[0]} == {"open", "closed"}):
        eyes = "one closed"
    if observation.eye_quality == "head_motion":
        eyes = f"stabilizing {vision.metrics.get('eye_motion_settle_remaining_seconds', 0.):.2f}s"
    yawn_state = f"confirm {status.yawn_candidate_seconds:.2f}/{config.monitor.yawn_enter_seconds:g}s" if status.yawn_state == "candidate" else status.yawn_state
    line(f"Eyes:{eyes} | Yawn:{yawn_state}", 71)
    branch = vision.metrics.get("eye_model_branch")
    suffix = "" if branch is None else f" | eye:{branch}"
    line(f"Eyes P(closed): {left[1]} / {right[1]}{suffix}", height - 86)
    line(f"Blink both:{status.blink_total} (5s:{status.blink_count}) | Eye cycles total:{status.left_eye_events + status.right_eye_events}", height - 61)
    raw = "?" if status.yawn_raw_probability is None else f"{status.yawn_raw_probability:.2f}"
    filtered = "?" if status.yawn_probability is None else f"{status.yawn_probability:.2f}"
    line(f"Yawn P raw:{raw} filtered:{filtered} | EMA:{config.monitor.yawn_smoothing_seconds:g}s", height - 36)
    metrics = vision.metrics
    if "sharpness" in metrics:
        line(f"Sharp face:{metrics['sharpness']:.1f}/{config.min_sharpness:g} eyes:{metrics['eye_sharpness_min']:.1f}/{config.min_eye_sharpness:g} | light:{metrics['eye_brightness_min']:.0f}", height - 11)
    elif vision.quality == "face_too_small" and metrics.get("face_min_side_pixels") is not None:
        line(f"Face min:{metrics['face_min_side_pixels']:.1f}/{config.min_face_size}px | MOVE CLOSER", height - 11)
    return output
