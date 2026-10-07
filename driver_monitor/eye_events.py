"""Independent eye cycles and paired blinks; no alarm confirmation lives here."""
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Closure:
    start: float
    end: float

    @property
    def duration(self):
        return self.end - self.start


class _EyeCycle:
    def __init__(self, config):
        self.config = config
        self.total = 0
        self.interrupt()

    def interrupt(self):
        self.state = self.started = self.last_confident = self.open_since = None
        self.uncertain = False

    def update(self, t, p_closed):
        if p_closed is None:
            self.interrupt()
            return None
        grace = self.config.eye_transition_grace_seconds
        if self.uncertain and self.last_confident is not None and t - self.last_confident > grace + 1e-9:
            self.interrupt()
        state = True if p_closed >= self.config.eye_confidence else False if 1 - p_closed >= self.config.eye_confidence else None
        if state is None:
            self.open_since = None
            self.uncertain = True
            if self.last_confident is not None and t - self.last_confident > grace + 1e-9:
                self.interrupt()
            return None
        event = None
        if state:
            self.open_since = None
            if self.state is False:
                self.started = t
        elif not state:
            if self.open_since is None:
                self.open_since = t
            if t - self.open_since < self.config.eye_event_open_seconds - 1e-9:
                self.last_confident, self.uncertain = t, False
                return None
            if self.state is True and self.started is not None:
                candidate = Closure(self.started, self.open_since)
                if candidate.duration >= self.config.min_blink_duration_seconds - 1e-9:
                    event = candidate
                    self.total += 1
            self.started = None
        self.state, self.last_confident, self.uncertain = state, t, False
        return event


class EyeEvents:
    """Count each eye's Open->Closed->Open cycle, and pair overlapping short ones.

    Brief ambiguous transitions may bridge an event. Missing/poor-quality/stale
    frames interrupt it. Only a paired short cycle contributes to blink rate;
    unilateral or long cycles are diagnostic counters only.
    """
    def __init__(self, config):
        self.config = config
        self.left, self.right = _EyeCycle(config), _EyeCycle(config)
        self.total = 0
        self.pending = (deque(), deque())
        self.valid_since = None

    def interrupt(self):
        self.left.interrupt()
        self.right.interrupt()
        for queue in self.pending:
            queue.clear()
        self.valid_since = None

    def update(self, t, left, right):
        events = (self.left.update(t, left), self.right.update(t, right))
        if self.left.state is None or self.right.state is None:
            self.valid_since = None
            for queue in self.pending:
                queue.clear()
            return False
        if self.valid_since is None:
            self.valid_since = t
        maximum = self.config.max_blink_duration_seconds
        for queue, event in zip(self.pending, events):
            while queue and t - queue[0].end > maximum + self.config.eye_transition_grace_seconds:
                queue.popleft()
            if event is not None and event.duration <= maximum + 1e-9:
                queue.append(event)
        for left_event in self.pending[0]:
            for right_event in self.pending[1]:
                overlap = min(left_event.end, right_event.end) - max(left_event.start, right_event.start)
                if overlap >= self.config.min_blink_duration_seconds - 1e-9:
                    self.pending[0].remove(left_event)
                    self.pending[1].remove(right_event)
                    self.total += 1
                    return True
        return False

    def baseline_ready(self, t):
        return self.valid_since is not None and t - self.valid_since >= 2 * self.config.blink_window_seconds - 1e-9
