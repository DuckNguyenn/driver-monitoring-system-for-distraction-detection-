"""Replay the quality-gate pattern captured in the user's camera session."""
import unittest
from unittest.mock import patch

import numpy as np

from driver_monitor.config import Config, ROOT, load_config
from driver_monitor.vision import Vision
from driver_monitor.eye_motion import EyeMotion


class CameraQualityTests(unittest.TestCase):
    def observe_metrics(self, config, face_sharpness, eye_sharpness, brightness=74., overexposed=.003):
        vision = object.__new__(Vision)
        vision.config = config
        vision.eye_motion = EyeMotion(config)
        vision.previous_box = None

        class Detector:
            def detect(self, image):
                face = [100, 50, 100, 110, 125, 80, 175, 80, 150, 95, 130, 120, 170, 120, .99]
                return None, np.array([face], dtype=np.float32)

        vision.detector = Detector()
        face_metrics = {"brightness_median": brightness, "sharpness": face_sharpness, "overexposed_ratio": overexposed}
        eye_metrics = {"brightness_median": brightness, "sharpness": eye_sharpness, "overexposed_ratio": .003}
        with patch("driver_monitor.vision.quality_metrics", side_effect=[face_metrics, eye_metrics, eye_metrics]):
            return vision.observe(np.zeros((480, 640, 3), dtype=np.uint8))

    def test_eye_cutoff_can_be_calibrated_separately_from_face(self):
        config = Config(min_eye_sharpness=6.)
        # Metrics from status records in 20261006T122039_722946Z.jsonl.
        # This replays threshold behavior, not image/classifier accuracy.
        for face_sharpness, eye_sharpness in (
                (39.50171695570812, 8.421974076165093),
                (23.258056854607062, 8.919794856388862),
                (32.59278826660186, 9.78703574448099)):
            with self.subTest(eye_sharpness=eye_sharpness):
                result = self.observe_metrics(config, face_sharpness, eye_sharpness)
                self.assertEqual(result.quality, "usable")

    def test_legacy_config_keeps_the_eye_gate(self):
        for config in (Config(), Config(min_sharpness=15.)):
            with self.subTest(threshold=config.min_sharpness):
                self.assertEqual(self.observe_metrics(config, 39.5, 8.4).quality, "blurry")

    def test_pc_profile_still_rejects_blur_darkness_and_overexposure(self):
        config = load_config(ROOT / "configs/camera_pc.yaml")
        for face_sharpness, eye_sharpness, brightness, overexposed, expected in (
                (19.9, 8.4, 74., .003, "blurry"),
                (39.5, 5.9, 74., .003, "blurry"),
                (39.5, 8.4, 24., .003, "too_dark"),
                (39.5, 8.4, 74., .61, "overexposed")):
            with self.subTest(expected=expected, face=face_sharpness, eyes=eye_sharpness):
                result = self.observe_metrics(config, face_sharpness, eye_sharpness, brightness, overexposed)
                self.assertEqual(result.quality, expected)

    def test_separate_eye_threshold_is_validated(self):
        for threshold in (0., -1., float("nan"), float("inf")):
            with self.subTest(threshold=threshold), self.assertRaisesRegex(ValueError, "min_eye_sharpness"):
                Config(min_eye_sharpness=threshold)


if __name__ == "__main__":
    unittest.main()
