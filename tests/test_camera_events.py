"""Camera-facing regressions for uncertain eye transitions and yawn reporting."""
import unittest

from driver_monitor import Monitor, MonitorConfig, Observation


def sample(t, closed_probability, yawn_probability=.1):
    eye = {"Closed": closed_probability, "Open": 1 - closed_probability}
    return Observation(t, eye, eye, {"yawn": yawn_probability, "no_yawn": 1 - yawn_probability})


class CameraEventTests(unittest.TestCase):
    def test_brief_ambiguous_transition_does_not_erase_a_confirmed_blink(self):
        monitor = Monitor()
        # Open -> transition -> Closed -> transition -> Open at 15 FPS.
        for t, p in ((0., .05), (1 / 15, .5), (2 / 15, .95), (3 / 15, .5), (4 / 15, .05)):
            status = monitor.update(sample(t, p))
            self.assertFalse(status.alert)
        self.assertEqual(status.blink_count, 1)

    def test_uncertain_eyes_preserve_independent_yawn_evidence(self):
        monitor = Monitor()
        for index in range(19):
            status = monitor.update(sample(index / 15, .5, .9))
            self.assertEqual(status.state, "UNKNOWN")
            self.assertFalse(status.alert)
        self.assertEqual(status.yawn_probability, .9)
        self.assertEqual(status.yawn_count, 1)
        self.assertEqual(status.yawn_state, "yawn")

    def test_left_wink_counts_left_cycle_without_a_bilateral_blink_or_alarm(self):
        monitor = Monitor()
        monitor.update(sample(0, .05))
        status = monitor.update(Observation(.1, {"Closed": .95, "Open": .05},
                                            {"Closed": .05, "Open": .95}, {"yawn": .1, "no_yawn": .9}))
        self.assertEqual(status.state, "UNKNOWN")
        self.assertFalse(status.alert)
        status = monitor.update(sample(.2, .05))
        self.assertEqual(status.left_eye_events, 1)
        self.assertEqual(status.right_eye_events, 0)
        self.assertEqual(status.blink_count, 0)
        self.assertEqual(status.blink_total, 0)

    def test_long_unilateral_closure_is_diagnostic_only(self):
        monitor = Monitor()
        monitor.update(sample(0, .05))
        for index in range(1, 25):
            status = monitor.update(Observation(index / 10, {"Closed": .95, "Open": .05},
                                                {"Closed": .05, "Open": .95}, {"yawn": .1, "no_yawn": .9}))
            self.assertFalse(status.alert)
        status = monitor.update(sample(2.5, .05))
        self.assertEqual(status.left_eye_events, 1)
        self.assertEqual(status.blink_total, 0)

    def test_slightly_asynchronous_eyes_pair_into_one_blink(self):
        monitor = Monitor()
        for t, left, right in ((0, .05, .05), (.05, .95, .05), (.1, .95, .95), (.15, .05, .95), (.2, .05, .05)):
            status = monitor.update(Observation(t, {"Closed": left, "Open": 1-left},
                                                {"Closed": right, "Open": 1-right}, {"yawn": .1, "no_yawn": .9}))
        self.assertEqual(status.blink_total, 1)
        self.assertEqual(status.blink_count, 1)
        self.assertEqual((status.left_eye_events, status.right_eye_events), (1, 1))

    def test_unknown_frames_do_not_bridge_a_long_eye_cycle(self):
        monitor = Monitor()
        for t, p in ((0., .05), (.1, .95), (.2, .5), (.3, .5), (.4, .05)):
            status = monitor.update(sample(t, p))
        self.assertEqual(status.blink_total, 0)
        self.assertEqual((status.left_eye_events, status.right_eye_events), (0, 0))

    def test_missing_quality_or_capture_gap_interrupts_all_event_candidates(self):
        for fault in ("no_face", "blurry", "stale_frame", "frame_gap"):
            monitor = Monitor()
            monitor.update(sample(0, .05, .9))
            monitor.update(sample(.1, .95, .9))
            t = .8 if fault == "frame_gap" else .2
            frame = sample(t, .05, .9)
            if fault == "stale_frame":
                frame = Observation(t, frame.left_eye, frame.right_eye, frame.yawn, age_seconds=.3)
            elif fault != "frame_gap":
                frame = Observation(t, quality=fault)
            monitor.update(frame)
            status = monitor.update(sample(t + .1, .05, .9))
            with self.subTest(fault=fault):
                self.assertEqual(status.blink_total, 0)
                self.assertEqual(status.yawn_count, 0)
                self.assertFalse(status.alert)

    def test_eye_uncertainty_still_restarts_the_long_closure_alarm(self):
        monitor = Monitor()
        for index in range(15):
            monitor.update(sample(index / 10, .95))
        self.assertFalse(monitor.update(sample(1.5, .5)).alert)
        for index in range(16, 31):
            self.assertFalse(monitor.update(sample(index / 10, .95)).alert)
        self.assertTrue(monitor.update(sample(3.1, .95)).alert)

    def test_confirmed_yawn_stays_one_event_when_raw_p_oscillates(self):
        monitor = Monitor(MonitorConfig(yawn_smoothing_seconds=.2))
        for index in range(31):
            status = monitor.update(sample(index / 15, .5, .9))
        self.assertEqual(status.yawn_count, 1)
        for index in range(31, 76):
            status = monitor.update(sample(index / 15, .5, .4 if index % 2 else .9))
            self.assertEqual(status.yawn_count, 1)
            self.assertEqual(status.yawn_state, "yawn")
            self.assertFalse(status.alert)
        self.assertGreater(status.yawn_probability, .4)
        self.assertLess(status.yawn_probability, .9)

    def test_time_based_smoothing_has_consistent_timing_across_fps(self):
        entered = []
        for fps in (5, 15, 30, 60):
            monitor = Monitor(MonitorConfig(yawn_smoothing_seconds=.2))
            monitor.update(sample(0, .05, .1))
            for index in range(1, 3 * fps + 1):
                status = monitor.update(sample(index / fps, .05, .9))
                if status.yawn_count:
                    entered.append(index / fps)
                    break
        self.assertEqual(len(entered), 4)
        self.assertLessEqual(max(entered) - min(entered), .2)
        self.assertTrue(all(1.2 <= t <= 1.5 for t in entered))

    def test_transient_high_yawn_p_cannot_confirm_an_event(self):
        monitor = Monitor(MonitorConfig(yawn_smoothing_seconds=.2))
        for index in range(91):
            status = monitor.update(sample(index / 30, .05, .9 if index == 30 else .1))
            self.assertEqual(status.yawn_count, 0)
            self.assertFalse(status.alert)

    def test_driver_change_clears_eye_cycle_totals_and_yawn_filter(self):
        monitor = Monitor(MonitorConfig(yawn_smoothing_seconds=.2))
        for t, p in ((0, .05), (.1, .95), (.2, .05)):
            status = monitor.update(sample(t, p, .9))
        self.assertEqual(status.blink_total, 1)
        frame = sample(.3, .05, .1)
        status = monitor.update(Observation(.3, frame.left_eye, frame.right_eye, frame.yawn, track_changed=True))
        self.assertEqual(status.blink_total, 0)
        self.assertEqual((status.left_eye_events, status.right_eye_events), (0, 0))
        self.assertEqual(status.yawn_probability, .1)

    def test_invalid_filter_or_grace_is_rejected(self):
        for changes in ({"yawn_smoothing_seconds": -.1}, {"yawn_smoothing_seconds": float("nan")},
                        {"eye_transition_grace_seconds": .3}, {"eye_transition_grace_seconds": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                MonitorConfig(**changes)


if __name__ == "__main__":
    unittest.main()
