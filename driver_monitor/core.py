"""Elapsed-time decisions. No camera, numpy, model or serial dependencies."""
from collections import deque
from dataclasses import dataclass
from math import expm1, isfinite
from typing import Mapping
from .eye_events import EyeEvents


@dataclass(frozen=True)
class MonitorConfig:
    eye_confidence: float = 0.8
    eye_closed_seconds: float = 1.5
    max_frame_gap_seconds: float = 0.25
    recovery_seconds: float = 1.0
    yawn_enter_probability: float = 0.70
    yawn_exit_probability: float = 0.35
    yawn_enter_seconds: float = 1.0
    yawn_exit_seconds: float = 0.5
    yawn_window_seconds: float = 60.0
    yawn_min_count: int = 2
    blink_window_seconds: float = 5.0
    blink_min_count: int = 4
    blink_increase_margin: int = 1
    min_blink_duration_seconds: float = 0.05
    max_blink_duration_seconds: float = 0.5
    eye_transition_grace_seconds: float = 0.15
    # Zero preserves unfiltered decision probabilities for older configs.
    yawn_smoothing_seconds: float = 0.0
    # Zero preserves the event policy for existing configurations.
    eye_event_open_seconds: float = 0.0

    def __post_init__(self):
        for name, value in vars(self).items():
            if not isinstance(value, (int, float)) or not isfinite(value) or value < 0 or (value == 0 and name not in ("yawn_smoothing_seconds", "eye_event_open_seconds")):
                raise ValueError(f"{name} must be finite and positive")
        for name in ("eye_confidence", "yawn_enter_probability", "yawn_exit_probability"):
            if getattr(self, name) > 1:
                raise ValueError(f"{name} must be <= 1")
        if self.eye_confidence <= 0.5:
            raise ValueError("eye_confidence must distinguish Open from Closed")
        if self.yawn_exit_probability >= self.yawn_enter_probability:
            raise ValueError("yawn exit must be lower than enter")
        if self.min_blink_duration_seconds >= self.max_blink_duration_seconds:
            raise ValueError("blink duration interval is empty")
        if self.eye_transition_grace_seconds > self.max_frame_gap_seconds:
            raise ValueError("eye transition grace must not exceed the maximum frame gap")
        if self.eye_event_open_seconds > self.max_frame_gap_seconds:
            raise ValueError("eye event open confirmation must not exceed the maximum frame gap")
        for name in ("blink_min_count", "blink_increase_margin", "yawn_min_count"):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise ValueError(f"{name} must be an integer")


@dataclass(frozen=True)
class Observation:
    timestamp: float
    left_eye: Mapping[str, float] | None = None
    right_eye: Mapping[str, float] | None = None
    yawn: Mapping[str, float] | None = None
    quality: str = "usable"
    age_seconds: float = 0.0
    track_changed: bool = False
    eye_quality: str = "usable"


@dataclass(frozen=True)
class Status:
    timestamp: float
    state: str
    alert: bool
    reasons: tuple[str, ...]
    eye_closed: bool | None
    eye_closed_seconds: float
    blink_count: int
    previous_blink_count: int
    blink_baseline_ready: bool
    yawn_state: str
    yawn_count: int
    yawn_probability: float | None
    blink_total: int = 0
    left_eye_events: int = 0
    right_eye_events: int = 0
    yawn_raw_probability: float | None = None
    yawn_candidate_seconds: float = 0.0
    blink_detected: bool = False

    @property
    def blink_count_5s(self):
        return self.blink_count

    @property
    def previous_blink_count_5s(self):
        return self.previous_blink_count


def probabilities(values, labels):
    """Validate distributions and canonicalize names without assuming class order."""
    if values is None:
        return None
    try:
        normalized = {str(k).casefold(): float(v) for k, v in values.items()}
        wanted = {label.casefold() for label in labels}
        if set(normalized) != wanted or len(normalized) != len(values):
            return None
        if any(not isfinite(v) or v < 0 or v > 1 for v in normalized.values()):
            return None
        if abs(sum(normalized.values()) - 1) > 0.001:
            return None
        return normalized
    except (TypeError, ValueError, AttributeError):
        return None


class Monitor:
    """Only consecutive, fresh observations can confirm an alarm.

    Timestamps are strictly increasing in the source clock. UNKNOWN immediately
    disables the alarm and interrupts its continuous confirmation. Independent
    valid modalities remain observable: uncertain eyes do not discard a valid
    mouth distribution. Frame faults interrupt all timers. Confirmed history is
    retained until expiry; changing the tracked driver clears all history.
    """

    def __init__(self, config: MonitorConfig | None = None):
        self.config = config or MonitorConfig()
        self._last = None
        self._blinks = deque()
        self._yawns = deque()
        self._yawn_active = False
        self._alarm = False
        self._alarm_reasons = ()
        self._eye_events = EyeEvents(self.config)
        self._interrupt()

    def _interrupt(self):
        self._closed_since = None
        self._yawn_enter_since = None
        self._yawn_exit_since = None
        self._recovery_since = None
        self._filtered_yawn = self._yawn_last = None
        self._eye_events.interrupt()

    def _update_yawn(self, t, raw):
        if raw is None:
            self._filtered_yawn = self._yawn_last = None
            self._yawn_enter_since = self._yawn_exit_since = None
            return None, "unknown", 0.0
        c = self.config
        if self._filtered_yawn is None or not c.yawn_smoothing_seconds:
            self._filtered_yawn = raw
        else:
            alpha = -expm1(-(t - self._yawn_last) / c.yawn_smoothing_seconds)
            self._filtered_yawn += alpha * (raw - self._filtered_yawn)
        self._yawn_last = t
        p = self._filtered_yawn
        if not self._yawn_active:
            self._yawn_exit_since = None
            if p >= c.yawn_enter_probability:
                if self._yawn_enter_since is None:
                    self._yawn_enter_since = t
                if t - self._yawn_enter_since >= c.yawn_enter_seconds - 1e-9:
                    self._yawn_active = True
                    self._yawns.append(t)
                    self._yawn_enter_since = None
            else:
                self._yawn_enter_since = None
        else:
            if p <= c.yawn_exit_probability:
                if self._yawn_exit_since is None:
                    self._yawn_exit_since = t
                if t - self._yawn_exit_since >= c.yawn_exit_seconds - 1e-9:
                    self._yawn_active = False
                    self._yawn_exit_since = None
            else:
                self._yawn_exit_since = None
        candidate = 0.0 if self._yawn_enter_since is None else t - self._yawn_enter_since
        state = "yawn" if self._yawn_active else "candidate" if self._yawn_enter_since is not None else "no_yawn"
        return p, state, candidate

    def update(self, observation: Observation) -> Status:
        c = self.config
        t = float(observation.timestamp)
        if not isfinite(t) or (self._last is not None and t <= self._last):
            raise ValueError("timestamps must be finite and strictly increasing")
        gap = self._last is not None and t - self._last > c.max_frame_gap_seconds + 1e-9
        self._last = t
        if observation.track_changed:
            self._blinks.clear()
            self._yawns.clear()
            self._yawn_active = False
            self._alarm = False
            self._eye_events = EyeEvents(c)
            self._interrupt()
        if gap:
            self._interrupt()
            self._alarm = False
        while self._blinks and self._blinks[0] < t - 2 * c.blink_window_seconds:
            self._blinks.popleft()
        while self._yawns and self._yawns[0] < t - c.yawn_window_seconds:
            self._yawns.popleft()
        left = probabilities(observation.left_eye, ("Open", "Closed"))
        right = probabilities(observation.right_eye, ("Open", "Closed"))
        mouth = probabilities(observation.yawn, ("no_yawn", "yawn"))
        closed = None
        if observation.eye_quality == "usable" and left is not None and right is not None:
            if min(left["closed"], right["closed"]) >= c.eye_confidence:
                closed = True
            elif min(left["open"], right["open"]) >= c.eye_confidence:
                closed = False
        reason = None
        if observation.quality != "usable":
            reason = observation.quality
        elif not isfinite(observation.age_seconds) or observation.age_seconds < 0 or observation.age_seconds > c.max_frame_gap_seconds:
            reason = "stale_frame"
        elif observation.eye_quality != "usable":
            reason = observation.eye_quality
        elif left is None or right is None or mouth is None:
            reason = "invalid_probabilities"
        elif closed is None:
            reason = "uncertain_eyes"
        elif gap:
            reason = "frame_gap"
        # Whole-frame faults interrupt both channels. Eye confidence does not
        # discard otherwise valid mouth evidence or per-eye diagnostic cycles.
        whole_frame_fault = (observation.quality != "usable" or not isfinite(observation.age_seconds)
                             or observation.age_seconds < 0 or observation.age_seconds > c.max_frame_gap_seconds
                             or reason == "frame_gap")
        blink = False
        if whole_frame_fault:
            self._interrupt()
            raw = None
        else:
            if observation.eye_quality != "usable":
                self._eye_events.interrupt()
            else:
                blink = self._eye_events.update(t, None if left is None else left["closed"], None if right is None else right["closed"])
            if blink:
                self._blinks.append(t)
            raw = None if mouth is None else mouth["yawn"]
        p, yawn_state, candidate = self._update_yawn(t, raw)
        current = sum(b >= t - c.blink_window_seconds for b in self._blinks)
        previous = len(self._blinks) - current
        baseline = self._eye_events.baseline_ready(t)
        details = dict(blink_total=self._eye_events.total, left_eye_events=self._eye_events.left.total,
                       right_eye_events=self._eye_events.right.total, yawn_raw_probability=raw,
                       yawn_candidate_seconds=candidate, blink_detected=blink)
        if reason:
            self._closed_since = self._recovery_since = None
            self._alarm = False
            self._alarm_reasons = ()
            return Status(t, "UNKNOWN", False, (reason,), None, 0.0, current, previous,
                          baseline, yawn_state, len(self._yawns), p, **details)
        if closed:
            if self._closed_since is None:
                self._closed_since = t
        elif self._closed_since is not None:
            self._closed_since = None
        closed_seconds = 0.0 if self._closed_since is None else t - self._closed_since
        rising = baseline and current >= c.blink_min_count and current >= previous + c.blink_increase_margin
        frequent = len(self._yawns) >= c.yawn_min_count
        reasons = []
        if frequent:
            reasons.append("frequent_yawning")
        if rising:
            reasons.append("blink_rate_increasing")
        if closed_seconds >= c.eye_closed_seconds - 1e-9:
            reasons.insert(0, "eyes_closed_too_long")
        trigger = "eyes_closed_too_long" in reasons or (frequent and rising)
        if trigger:
            self._alarm = True
            self._alarm_reasons = tuple(reasons)
            self._recovery_since = None
        elif self._alarm:
            if self._recovery_since is None:
                self._recovery_since = t
            if t - self._recovery_since >= c.recovery_seconds - 1e-9:
                self._alarm = False
                self._alarm_reasons = ()
                self._recovery_since = None
        if self._alarm and not trigger:
            reasons = list(self._alarm_reasons) + ["recovering"]
        state = "ALERT" if self._alarm else "WARNING" if reasons else "NORMAL"
        return Status(t, state, self._alarm, tuple(reasons), closed, closed_seconds,
                      current, previous, baseline, yawn_state,
                      len(self._yawns), p, **details)
