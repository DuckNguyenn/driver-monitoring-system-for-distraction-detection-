"""Pose transitions must not masquerade as eye closure events."""
import json
import unittest
from dataclasses import replace
import cv2
import numpy as np

from driver_monitor import Monitor, Observation
from driver_monitor.core import MonitorConfig
from driver_monitor.config import ROOT, load_config
from driver_monitor.models import Classifier, sha256
from driver_monitor.vision import Vision
from driver_monitor.eye_motion import EyeMotion


class HeadMotionTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / "tests/fixtures/eye_motion/source.json").is_file(),
                         "Local face regression images are not distributed with the repository")
    def test_real_open_face_roll_and_return_does_not_create_an_eye_cycle(self):
        fixture = ROOT / "tests/fixtures/eye_motion"
        provenance = json.loads((fixture / "source.json").read_text())
        path = fixture / provenance["file"]
        self.assertEqual(sha256(path), provenance["sha256"])
        image = cv2.imread(str(path))
        height, width = image.shape[:2]
        rotated = cv2.warpAffine(image, cv2.getRotationMatrix2D((width/2, height/2), 15, 1),
                                 (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        config = load_config(ROOT / "configs/camera_pc.yaml")
        vision, monitor = Vision(config), Monitor(config.monitor)
        model = Classifier(config.manifest, "eye", "onnx")
        try:
            # Hold the rotated pose and the return long enough to confirm an
            # Open->Closed->Open event if movement information is lost.
            for confirmation in (0., .1):
                with self.subTest(open_confirmation=confirmation):
                    vision = Vision(config)
                    monitor = Monitor(replace(config.monitor, eye_event_open_seconds=confirmation))
                    motion_frames = 0
                    for index in range(13):
                        t = index / 10
                        frame = rotated if 3 <= index <= 5 else image
                        result = vision.observe(frame, timestamp=t)
                        self.assertEqual(result.quality, "usable")
                        eyes = [model.predict(crop) for crop in result.crops[:2]]
                        motion_frames += result.eye_quality == "head_motion"
                        status = monitor.update(Observation(t, *eyes, {"yawn": .1, "no_yawn": .9},
                                                            track_changed=result.track_changed, eye_quality=result.eye_quality))
                    self.assertGreater(motion_frames, 0)
                    self.assertEqual(result.eye_quality, "usable")
                    self.assertEqual(status.left_eye_events + status.right_eye_events, 0)
                    self.assertEqual(status.blink_total, 0)
        finally:
            model.close()

    def pose(self):
        return np.array([80, 50, 160, 180, 110, 100, 170, 100, 140, 135, 120, 175, 160, 175, .99], float)

    def test_pitch_like_nose_shift_and_head_translation_interrupt_eye_evidence(self):
        config = load_config(ROOT / "configs/camera_pc.yaml")
        for movement in ("pitch", "translation", "zoom"):
            with self.subTest(movement=movement):
                tracker = EyeMotion(config)
                original = self.pose()
                self.assertEqual(tracker.update(original, 0)[0], "usable")
                changed = original.copy()
                if movement == "pitch":
                    changed[9] += 8
                elif movement == "translation":
                    changed[4:14:2] += 8
                else:
                    changed[4:14] = ((changed[4:14].reshape(5, 2) - [140, 135]) * 1.15 + [140, 135]).reshape(-1)
                quality, metrics = tracker.update(changed, .1)
                self.assertEqual(quality, "head_motion")
                self.assertAlmostEqual(metrics["eye_motion_roll_change_degrees"], 0)

    def test_motion_settles_with_time_at_variable_fps(self):
        config = load_config(ROOT / "configs/camera_pc.yaml")
        for fps in (5, 15, 30, 60):
            tracker = EyeMotion(config)
            original = self.pose()
            tracker.update(original, 0)
            changed = original.copy()
            changed[4:14:2] += 8
            entered = 1 / fps
            self.assertEqual(tracker.update(changed, entered)[0], "head_motion")
            for index in range(2, fps + 1):
                t = index / fps
                quality, _ = tracker.update(changed, t)
                expected = "head_motion" if t < entered + config.eye_motion_settle_seconds - 1e-9 else "usable"
                with self.subTest(fps=fps, time=t):
                    self.assertEqual(quality, expected)

    def test_gradual_translation_is_measured_over_a_time_window(self):
        tracker = EyeMotion(load_config(ROOT / "configs/camera_pc.yaml"))
        original = self.pose()
        self.assertEqual(tracker.update(original, 0)[0], "usable")
        for index in range(1, 4):
            changed = original.copy()
            changed[4:14:2] += 2 * index
            quality, _ = tracker.update(changed, index / 15)
        self.assertEqual(quality, "head_motion")

    def test_stable_pose_and_small_landmark_noise_stay_usable(self):
        tracker = EyeMotion(load_config(ROOT / "configs/camera_pc.yaml"))
        original = self.pose()
        for index in range(30):
            jittered = original.copy()
            jittered[4:14] += .2 if index % 2 else -.2
            self.assertEqual(tracker.update(jittered, index / 15)[0], "usable")

    def test_movement_does_not_count_cycles_but_keeps_independent_yawn_evidence(self):
        config = MonitorConfig(eye_event_open_seconds=.1)
        monitor = Monitor(config)
        opened, closed = {"Closed": .05, "Open": .95}, {"Closed": .95, "Open": .05}
        for index in range(31):
            values = opened if index < 3 or index >= 8 else closed
            status = monitor.update(Observation(index / 15, values, opened, {"yawn": .9, "no_yawn": .1},
                                                eye_quality="head_motion" if 3 <= index <= 8 else "usable"))
            self.assertFalse(status.alert)
        self.assertEqual(status.left_eye_events + status.right_eye_events, 0)
        self.assertEqual(status.yawn_count, 1)
        self.assertEqual(status.blink_total, 0)

    def test_one_frame_open_spike_does_not_split_a_closure_cycle(self):
        monitor = Monitor(MonitorConfig(eye_event_open_seconds=.1))
        opened, closed = {"Closed": .05, "Open": .95}, {"Closed": .95, "Open": .05}
        for index in range(15):
            values = opened if index < 3 or index == 5 or index >= 9 else closed
            status = monitor.update(Observation(index / 15, values, opened, {"yawn": .1, "no_yawn": .9}))
            if index <= 9:
                self.assertEqual(status.left_eye_events, 0)
        self.assertEqual(status.left_eye_events, 1)
        self.assertEqual(status.blink_total, 0)

    def test_confirmed_real_blink_and_long_closure_alarm_still_work(self):
        config = MonitorConfig(eye_event_open_seconds=.1)
        for fps in (5, 15, 30, 60):
            monitor = Monitor(config)
            for index in range(3 * fps + 1):
                t = index / fps
                p = .95 if 1 <= t < 1.2 else .05
                eye = {"Closed": p, "Open": 1-p}
                status = monitor.update(Observation(t, eye, eye, {"yawn": .1, "no_yawn": .9}))
            with self.subTest(fps=fps):
                self.assertEqual(status.blink_total, 1)
                self.assertEqual((status.left_eye_events, status.right_eye_events), (1, 1))
        monitor = Monitor(config)
        eye = {"Closed": .95, "Open": .05}
        for index in range(16):
            status = monitor.update(Observation(index / 10, eye, eye, {"yawn": .1, "no_yawn": .9}))
        self.assertTrue(status.alert)

    def test_motion_settings_and_open_confirmation_are_validated(self):
        from driver_monitor.config import Config
        for kwargs in ({"eye_motion_settle_seconds": 0}, {"eye_motion_max_roll_degrees": float("nan")},
                       {"eye_motion_max_shift_ratio": 2}, {"eye_motion_window_seconds": -1}):
            with self.assertRaises(ValueError):
                Config(**kwargs)
        for value in (-.1, float("nan"), .5):
            with self.assertRaises(ValueError):
                MonitorConfig(eye_event_open_seconds=value)


if __name__ == "__main__":
    unittest.main()
