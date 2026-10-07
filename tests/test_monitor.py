import math
import unittest
from driver_monitor import Monitor, MonitorConfig, Observation


def obs(t, closed=False, yawn=0.0, **kwargs):
    values = {"Closed": .95 if closed else .05, "Open": .05 if closed else .95}
    return Observation(t, values, values, {"yawn": yawn, "no_yawn": 1 - yawn}, **kwargs)


class MonitorTests(unittest.TestCase):
    def test_closure_threshold_and_one_second_recovery(self):
        m = Monitor()
        for i in range(16):
            status = m.update(obs(i / 10, True))
        self.assertTrue(status.alert)
        self.assertIn("eyes_closed_too_long", status.reasons)
        for i in range(16, 26):
            self.assertTrue(m.update(obs(i / 10)).alert)
        self.assertFalse(m.update(obs(2.6)).alert)

    def test_short_closure_is_blink_long_closure_is_not(self):
        m = Monitor()
        m.update(obs(0))
        m.update(obs(.1, True))
        self.assertEqual(m.update(obs(.2)).blink_count, 1)
        for i in range(3, 10):
            m.update(obs(i / 10, True))
        self.assertEqual(m.update(obs(1)).blink_count, 1)

    def test_missing_and_stale_inputs_stop_alarm_without_faking_open_eye(self):
        for mode in ("missing", "stale", "quality", "confidence"):
            m = Monitor()
            for i in range(17):
                m.update(obs(i / 10, True))
            sample = Observation(1.7) if mode == "missing" else obs(1.7, True, age_seconds=.3) if mode == "stale" else obs(1.7, True, quality="too_dark") if mode == "quality" else Observation(1.7, {"Open": .5, "Closed": .5}, {"Open": .5, "Closed": .5}, {"yawn": 0., "no_yawn": 1.})
            status = m.update(sample)
            self.assertEqual(status.state, "UNKNOWN")
            self.assertIsNone(status.eye_closed)
            self.assertFalse(status.alert)
            self.assertEqual(m.update(obs(1.8)).blink_count, 0)

    def test_long_frame_gap_does_not_confirm_closure(self):
        m = Monitor()
        m.update(obs(0, True))
        status = m.update(obs(5, True))
        self.assertFalse(status.alert)
        self.assertEqual(status.state, "UNKNOWN")
        self.assertEqual(status.eye_closed_seconds, 0)
        self.assertFalse(m.update(obs(5.1, True)).alert)

    def test_yawn_is_time_based_at_5_10_15_30_fps_and_one_event_never_alerts(self):
        for fps in (5, 10, 15, 30):
            m = Monitor()
            entered = None
            for i in range(3 * fps + 1):
                status = m.update(obs(i / fps, yawn=.9))
                if status.yawn_count and entered is None:
                    entered = i / fps
                self.assertFalse(status.alert)
            self.assertAlmostEqual(entered, 1., places=6)
            self.assertEqual(status.yawn_count, 1)

    def test_two_distinct_yawns_warn_then_expire(self):
        m = Monitor()
        for i in range(51):
            t = i / 10
            p = .9 if t <= 1.3 or 2.0 <= t <= 3.3 else .1
            status = m.update(obs(t, yawn=p))
        self.assertEqual(status.yawn_count, 2)
        self.assertEqual(status.state, "WARNING")
        self.assertFalse(status.alert)
        for i in range(51, 642):
            status = m.update(obs(i / 10))
        self.assertEqual(status.yawn_count, 0)

    def test_combined_yawns_and_increasing_blinks_alert_after_full_baseline(self):
        for with_yawns in (False, True):
            m = Monitor()
            for i in range(101):
                t = i / 10
                closing = any(start <= t < start + .15 for start in (1., 3., 6., 7., 8., 9.))
                p = .9 if with_yawns and (t <= 1.3 or 2 <= t <= 3.3) else .0
                status = m.update(obs(t, closing, p))
                if t < 10:
                    self.assertFalse(status.blink_baseline_ready)
            self.assertEqual(status.blink_count, 4)
            self.assertEqual(status.previous_blink_count, 2)
            self.assertTrue(status.blink_baseline_ready)
            self.assertIn("blink_rate_increasing", status.reasons)
            self.assertEqual(status.alert, with_yawns)

    def test_loss_during_yawn_does_not_count_same_yawn_twice(self):
        m = Monitor()
        for i in range(12):
            m.update(obs(i / 10, yawn=.9))
        m.update(Observation(1.2, quality="no_face"))
        for i in range(13, 30):
            status = m.update(obs(i / 10, yawn=.9))
        self.assertEqual(status.yawn_count, 1)

    def test_driver_change_clears_history(self):
        m = Monitor()
        for i in range(12):
            m.update(obs(i / 10, yawn=.9))
        status = m.update(obs(1.2, track_changed=True))
        self.assertEqual(status.yawn_count, 0)
        self.assertFalse(status.blink_baseline_ready)

    def test_invalid_probabilities_and_timestamps(self):
        m = Monitor()
        status = m.update(Observation(0, {"Closed": math.nan, "Open": .5}))
        self.assertEqual(status.state, "UNKNOWN")
        for t in (0., -.1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                m.update(obs(t))
        for change in ({"yawn_exit_probability": .8}, {"blink_min_count": 1.5}, {"eye_confidence": .5}, {"recovery_seconds": 0}):
            with self.assertRaises(ValueError):
                MonitorConfig(**change)
