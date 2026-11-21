"""Less restrictive pose filtering must recover blinks without accepting bad frames."""
import json
import math
import unittest
from dataclasses import replace
from pathlib import Path

from driver_monitor.config import Config, load_config
from driver_monitor.core import Monitor, MonitorConfig, Observation
from driver_monitor.eye_motion import EyeMotion


def pose():
    return [80., 50., 160., 180., 110., 100., 170., 100., 140., 135., 120., 175., 160., 175., .99]


def candidate():
    return Config(monitor=MonitorConfig(eye_event_open_seconds=.1),
                  eye_motion_max_shift_ratio=.3, eye_motion_max_roll_degrees=6.,
                  eye_motion_settle_seconds=.15, eye_motion_mode="pose",
                  eye_motion_smoothing_seconds=.1)


class EyeMotionProfileTests(unittest.TestCase):
    def test_pose_filter_ignores_uniform_image_translation_and_scale(self):
        tracker = EyeMotion(candidate())
        base = pose()
        for index in range(60):
            face = base.copy()
            scale = 1. + .3 * math.sin(index)
            for n in range(4, 14, 2):
                face[n] = face[n] * scale + 30 * math.sin(index / 3)
                face[n + 1] = face[n + 1] * scale + 20 * math.cos(index / 3)
            self.assertEqual(tracker.update(face, index / 60)[0], "usable")

    def test_smoothing_keeps_a_real_blink_during_small_landmark_jitter(self):
        config = candidate()
        config.eye_motion_max_shift_ratio = .08  # Same threshold as the old profile.
        tracker, monitor = EyeMotion(config), Monitor(config.monitor)
        for index in range(90):
            face = pose()
            face[9] += 3 if index % 2 else -3
            quality, _ = tracker.update(face, index / 60)
            p = .99 if 45 <= index < 51 else .01
            eye = {"Closed": p, "Open": 1-p}
            status = monitor.update(Observation(index / 60, eye, eye,
                {"yawn": .01, "no_yawn": .99}, eye_quality=quality))
        self.assertEqual(status.blink_total, 1)
        self.assertEqual((status.left_eye_events, status.right_eye_events), (1, 1))

    def test_short_real_trace_recovers_the_visually_reviewed_blink(self):
        trace = json.loads((Path(__file__).parent / "data/motion_blink_trace.json").read_text())
        baseline = candidate()
        baseline.eye_motion_mode = "geometry"
        baseline.eye_motion_smoothing_seconds = 0.
        baseline.eye_motion_max_shift_ratio = .08
        baseline.eye_motion_max_roll_degrees = 3.
        baseline.eye_motion_settle_seconds = .35
        for config, expected in ((baseline, 0), (candidate(), 1)):
            tracker, monitor = EyeMotion(config), Monitor(config.monitor)
            for t, landmarks, left, right in trace["rows"]:
                face = pose()
                face[4:10] = landmarks
                quality, _ = tracker.update(face, t)
                status = monitor.update(Observation(t,
                    {"Closed": left, "Open": 1-left}, {"Closed": right, "Open": 1-right},
                    {"yawn": .01, "no_yawn": .99}, eye_quality=quality))
            self.assertEqual(status.blink_total, expected)

    def test_large_roll_still_interrupts_false_closure_at_variable_fps(self):
        for fps in (5, 15, 30, 60):
            config = candidate()
            tracker, monitor = EyeMotion(config), Monitor(config.monitor)
            blocked = 0
            for index in range(2 * fps + 1):
                t, face = index / fps, pose()
                rotating = .6 <= t < .9
                if rotating:
                    a = math.radians(15)
                    for n in range(4, 14, 2):
                        x, y = face[n]-140, face[n+1]-135
                        face[n] = 140 + x*math.cos(a)-y*math.sin(a)
                        face[n+1] = 135 + x*math.sin(a)+y*math.cos(a)
                quality, _ = tracker.update(face, t)
                blocked += quality == "head_motion"
                p = .99 if rotating else .01
                eye = {"Closed": p, "Open": 1-p}
                status = monitor.update(Observation(t, eye, eye,
                    {"yawn": .01, "no_yawn": .99}, eye_quality=quality))
            with self.subTest(fps=fps):
                self.assertGreater(blocked, 0)
                self.assertEqual(status.blink_total, 0)
                self.assertEqual(status.left_eye_events + status.right_eye_events, 0)

    def test_large_nose_displacement_still_blocks_pose_change(self):
        tracker = EyeMotion(candidate())
        tracker.update(pose(), 0.)
        changed = pose()
        changed[9] += 30
        quality, _ = tracker.update(changed, .2)
        self.assertEqual(quality, "head_motion")

    def test_gap_and_explicit_reset_clear_filter_history(self):
        tracker = EyeMotion(candidate())
        tracker.update(pose(), 0.)
        changed = pose()
        changed[9] += 30
        self.assertEqual(tracker.update(changed, 1.)[0], "usable")
        tracker.reset()
        self.assertEqual(tracker.update(pose(), 1.1)[0], "usable")

    def test_pose_profile_does_not_override_missing_or_bad_observations(self):
        config = candidate()
        for fault in ("no_face", "too_dark", "blurry", "invalid_landmarks"):
            monitor = Monitor(config.monitor)
            eye = {"Closed": .99, "Open": .01}
            for index in range(31):
                status = monitor.update(Observation(index / 15, eye, eye,
                    {"yawn": .99, "no_yawn": .01}, quality=fault, eye_quality=fault))
            self.assertEqual(status.state, "UNKNOWN")
            self.assertFalse(status.alert)
            self.assertEqual(status.blink_total, 0)

    def test_configuration_validation_and_fingerprints(self):
        for kwargs in ({"eye_motion_mode": "off"}, {"eye_motion_smoothing_seconds": -1},
                       {"eye_motion_smoothing_seconds": float("nan")},
                       {"eye_motion_smoothing_seconds": .5}):
            with self.assertRaises(ValueError):
                Config(**kwargs)
        config = Config()
        self.assertNotEqual(config.fingerprint(), replace(config, eye_motion_mode="pose").fingerprint())
        self.assertNotEqual(config.fingerprint(), replace(config, eye_motion_smoothing_seconds=.1).fingerprint())

    def test_candidate_keeps_source_models_quality_and_decision_settings(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "models/yawn_kaggle_near_medium/runtime.yaml"
        if not source.exists():
            self.skipTest("Local near/medium source profile is not distributed")
        baseline = load_config(source)
        selected = load_config(root / "configs/camera_video_pose_candidate.yaml")
        changed = {key for key in vars(baseline) if getattr(baseline, key) != getattr(selected, key)}
        self.assertEqual(changed, {"eye_motion_mode", "eye_motion_smoothing_seconds",
            "eye_motion_settle_seconds", "eye_motion_max_shift_ratio", "eye_motion_max_roll_degrees"})


if __name__ == "__main__":
    unittest.main()
