"""Face-size abstention must not be reported as a detector miss."""
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from driver_monitor import Monitor, Observation
from driver_monitor.config import Config, ROOT
from driver_monitor.vision import Vision


class FaceSizeGateTests(unittest.TestCase):
    def observe(self, rows, config=None):
        config = config or Config(min_eye_sharpness=6)
        detector = Mock()
        # Rows are already in YuNet's padded 320x320 input coordinates.
        detector.detect.return_value = (1, rows)
        frame = np.random.default_rng(42).integers(45, 180, (480, 640, 3), dtype=np.uint8)
        with patch("driver_monitor.vision.cv2.FaceDetectorYN.create", return_value=detector):
            return Vision(config).observe(frame, 0.)

    def row(self, width=74., x=200.):
        original = np.array([x, 120, width, 100, x+15, 145, x+width-15, 145,
                             x+width/2, 165, x+20, 190, x+width-20, 190, .93], dtype=np.float32)
        row = original.copy()
        row[:14] *= .5
        row[[1, 5, 7, 9, 11, 13]] += 40  # 640x480 -> 320x240, 40px top padding
        return row

    def test_detected_small_face_reports_size_and_keeps_unknown(self):
        result = self.observe(np.array([self.row()]))
        self.assertEqual(result.quality, "face_too_small")
        self.assertIsNone(result.crops)
        self.assertAlmostEqual(result.confidence, .93, places=5)
        self.assertAlmostEqual(result.metrics["face_min_side_pixels"], 74.)
        self.assertEqual(result.metrics["min_face_size_threshold"], 80)
        self.assertEqual(result.metrics["detected_face_count"], 1)
        self.assertEqual(result.metrics["accepted_face_count"], 0)
        # Even supplied classifier probabilities cannot create evidence through a size fault.
        monitor = Monitor()
        for index in range(61):
            status = monitor.update(Observation(index / 30, {"Closed": 1., "Open": 0.},
                                    {"Closed": 1., "Open": 0.}, {"yawn": 1., "no_yawn": 0.},
                                    quality=result.quality))
        self.assertEqual(status.state, "UNKNOWN")
        self.assertEqual(status.reasons, ("face_too_small",))
        self.assertFalse(status.alert)
        self.assertEqual(status.yawn_count, 0)
        self.assertIsNone(status.yawn_probability)

    def test_face_exactly_at_threshold_uses_original_pixels(self):
        result = self.observe(np.array([self.row(width=80.)]))
        self.assertEqual(result.quality, "usable")
        self.assertAlmostEqual(result.metrics["face_min_side_pixels"], 80.)
        self.assertEqual(result.metrics["accepted_face_count"], 1)
        self.assertIsNotNone(result.crops)

    def test_genuine_detector_miss_still_reports_no_face(self):
        result = self.observe(None)
        self.assertEqual(result.quality, "no_face")
        self.assertEqual(result.metrics["detected_face_count"], 0)
        self.assertIsNone(result.metrics["face_min_side_pixels"])

    def test_small_face_outside_driver_roi_is_not_a_driver_size_fault(self):
        result = self.observe(np.array([self.row(x=400.)]),
                              Config(driver_roi=(0., 0., .4, 1.), min_eye_sharpness=6))
        self.assertEqual(result.quality, "no_face")
        self.assertEqual(result.metrics["faces_in_driver_roi"], 0)
        self.assertIsNone(result.metrics["face_min_side_pixels"])

    @unittest.skipUnless((ROOT / "data_collection/yawn_distance/videos/20261010T163038_149200Z.avi").is_file(),
                         "Private far-camera recording is not distributed")
    def test_real_far_recording_abstains_with_correct_reason(self):
        cap = cv2.VideoCapture(str(ROOT / "data_collection/yawn_distance/videos/20261010T163038_149200Z.avi"))
        try:
            ok, frame = cap.read()
        finally:
            cap.release()
        self.assertTrue(ok)
        result = Vision(Config(min_eye_sharpness=6)).observe(frame, 0.)
        self.assertEqual(result.quality, "face_too_small")
        self.assertLess(result.metrics["face_min_side_pixels"], 80.)
        self.assertGreater(result.confidence, .8)
        self.assertIsNone(result.crops)


if __name__ == "__main__":
    unittest.main()
