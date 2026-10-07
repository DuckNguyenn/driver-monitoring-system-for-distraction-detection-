"""Regression at the real pixel -> classifier -> monitoring seam."""
import unittest
import cv2

from driver_monitor import Monitor, Observation
from driver_monitor.config import ROOT, load_config
from driver_monitor.models import Classifier
from driver_monitor.vision import Vision


@unittest.skipUnless(all((ROOT / 'tests/fixtures/eyes' / name).is_file()
                         for name in ('open_narrow_face.jpg', 'closed_eye.jpg')),
                     'Local face regression images are not distributed with the repository')
class EyeClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / 'configs/camera_pc.yaml')
        cls.model = Classifier(cls.config.manifest, 'eye', 'onnx')
        image = cv2.imread(str(ROOT / 'tests/fixtures/eyes/open_narrow_face.jpg'))
        cls.face = Vision(cls.config).observe(image)
        cls.open_eyes = [cls.model.predict(crop) for crop in cls.face.crops[:2]]
        cls.closed_eye = cls.model.predict(cv2.imread(str(ROOT / 'tests/fixtures/eyes/closed_eye.jpg')))

    @classmethod
    def tearDownClass(cls):
        cls.model.close()

    def test_real_open_eyes_are_not_classified_as_closed(self):
        self.assertEqual(self.face.quality, 'usable')
        for probabilities in self.open_eyes:
            self.assertGreaterEqual(probabilities['Open'], .8, probabilities)

    def test_one_closed_eye_plus_real_open_crop_never_triggers_both_closed(self):
        # Mixed real eye crops isolate the user's false bilateral-closure pattern.
        # This is a classifier regression, not a natural recorded wink clip.
        self.assertGreaterEqual(self.closed_eye['Closed'], .8, self.closed_eye)
        for side in range(2):
            monitor = Monitor(self.config.monitor)
            eyes = [self.open_eyes[side], self.closed_eye]
            for frame in range(61):
                status = monitor.update(Observation(frame / 30, *eyes, {'no_yawn': 1., 'yawn': 0.}))
                self.assertIsNot(status.eye_closed, True, self.open_eyes[side])
                self.assertFalse(status.alert)

    def test_true_two_closed_eyes_still_trigger_prolonged_closure(self):
        monitor = Monitor(self.config.monitor)
        for frame in range(61):
            status = monitor.update(Observation(frame / 30, self.closed_eye, self.closed_eye,
                                                {'no_yawn': 1., 'yawn': 0.}))
        self.assertTrue(status.alert)
        self.assertIn('eyes_closed_too_long', status.reasons)

    def test_real_crop_wink_counts_one_cycle_without_paired_blink(self):
        monitor = Monitor(self.config.monitor)
        for frame in range(45):
            eyes = list(self.open_eyes)
            if 15 <= frame < 24:
                eyes[0] = self.closed_eye
            status = monitor.update(Observation(frame / 30, *eyes, {'no_yawn': 1., 'yawn': 0.}))
            self.assertIsNot(status.eye_closed, True)
            self.assertFalse(status.alert)
        self.assertEqual(status.left_eye_events, 1)
        self.assertEqual(status.right_eye_events, 0)
        self.assertEqual(status.blink_total, 0)

    def test_real_crop_short_bilateral_closure_counts_one_blink(self):
        monitor = Monitor(self.config.monitor)
        for frame in range(45):
            eyes = [self.closed_eye, self.closed_eye] if 15 <= frame < 24 else self.open_eyes
            status = monitor.update(Observation(frame / 30, *eyes, {'no_yawn': 1., 'yawn': 0.}))
            self.assertFalse(status.alert)
        self.assertEqual(status.blink_total, 1)


if __name__ == '__main__':
    unittest.main()
