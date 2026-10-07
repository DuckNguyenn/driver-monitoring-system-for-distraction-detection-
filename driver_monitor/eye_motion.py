"""Identify unstable eye observations from YuNet geometry, not eyelid scores."""
from collections import deque
from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite


@dataclass(frozen=True)
class EyePose:
    center: tuple[float, float]
    distance: float
    roll: float
    nose_relative: tuple[float, float]

    @classmethod
    def from_face(cls, face):
        ax, ay, bx, by, nx, ny = map(float, face[4:10])
        distance = hypot(bx - ax, by - ay)
        if not isfinite(distance) or distance <= 0:
            raise ValueError("invalid eye pose")
        ex, ey = (ax + bx) / 2, (ay + by) / 2
        return cls(((ex + nx) / 2, (ey + ny) / 2), distance,
                   degrees(atan2(by - ay, bx - ax)), ((nx - ex) / distance, (ny - ey) / distance))


class EyeMotion:
    """Pause eye events across movement, including gradual changes over a window.

    Five landmarks provide motion cues, not calibrated 3-D pitch/yaw angles.
    Omitting timestamps disables temporal checks for independent static images.
    """
    def __init__(self, config):
        self.config = config
        self.reset()

    def reset(self):
        self.history = deque()
        self.until = None

    def update(self, face, timestamp=None):
        pose = EyePose.from_face(face)
        metrics = {"eye_roll_degrees": pose.roll, "eye_distance_pixels": pose.distance,
                   "eye_motion_shift_ratio": 0., "eye_motion_shape_ratio": 0.,
                   "eye_motion_scale_ratio": 0., "eye_motion_roll_change_degrees": 0.,
                   "eye_motion_settle_remaining_seconds": 0.}
        if timestamp is None:
            return "usable", metrics
        t = float(timestamp)
        if not isfinite(t):
            raise ValueError("nonfinite eye motion timestamp")
        if self.history and (t <= self.history[-1][0] or t - self.history[-1][0] > self.config.monitor.max_frame_gap_seconds):
            self.reset()
        while self.history and t - self.history[0][0] > self.config.eye_motion_window_seconds + 1e-9:
            self.history.popleft()
        for _, previous in self.history:
            scale = (previous.distance + pose.distance) / 2
            metrics["eye_motion_shift_ratio"] = max(metrics["eye_motion_shift_ratio"],
                hypot(pose.center[0] - previous.center[0], pose.center[1] - previous.center[1]) / scale)
            metrics["eye_motion_shape_ratio"] = max(metrics["eye_motion_shape_ratio"],
                hypot(pose.nose_relative[0] - previous.nose_relative[0], pose.nose_relative[1] - previous.nose_relative[1]))
            metrics["eye_motion_scale_ratio"] = max(metrics["eye_motion_scale_ratio"], abs(pose.distance - previous.distance) / scale)
            metrics["eye_motion_roll_change_degrees"] = max(metrics["eye_motion_roll_change_degrees"],
                abs((pose.roll - previous.roll + 180) % 360 - 180))
        shifted = max(metrics[k] for k in ("eye_motion_shift_ratio", "eye_motion_shape_ratio", "eye_motion_scale_ratio"))
        moving = (shifted >= self.config.eye_motion_max_shift_ratio or
                  metrics["eye_motion_roll_change_degrees"] >= self.config.eye_motion_max_roll_degrees)
        if moving:
            self.until = t + self.config.eye_motion_settle_seconds
            # A stable new pose must not keep comparing against the old pose.
            self.history.clear()
        self.history.append((t, pose))
        remaining = 0. if self.until is None else max(0., self.until - t)
        metrics["eye_motion_settle_remaining_seconds"] = remaining
        return ("head_motion" if remaining > 1e-9 else "usable"), metrics
