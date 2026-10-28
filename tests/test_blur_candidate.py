"""Known real eye pixels after native-resolution blur, through the new profile."""
import unittest
import cv2

from driver_monitor import Monitor, Observation
from driver_monitor.blur import STRESS_BLURS, apply_blur
from driver_monitor.config import ROOT, load_config
from driver_monitor.models import Classifier
from driver_monitor.vision import Vision


@unittest.skipUnless(all(p.is_file() for p in (
    ROOT / "configs/camera_blur_candidate.yaml",
    ROOT / "tests/fixtures/eyes/open_narrow_face.jpg",
    ROOT / "tests/fixtures/eyes/closed_eye.jpg")),
    "Blur candidate and private eye regression images required")
class BlurCandidatePixels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "configs/camera_blur_candidate.yaml")
        cls.model = Classifier(cls.config.manifest, "eye", "onnx")

    @classmethod
    def tearDownClass(cls):
        cls.model.close()

    def test_usable_blurred_open_face_does_not_become_closed(self):
        image = cv2.imread(str(ROOT / "tests/fixtures/eyes/open_narrow_face.jpg"))
        for params in STRESS_BLURS:
            with self.subTest(blur=params):
                blurred = apply_blur(image, params)
                result = Vision(self.config).observe(blurred)
                if result.quality != "usable":
                    # Lost visual evidence must abstain instead of inventing
                    # two closed eyes. The live loop never predicts these ROIs.
                    self.assertIn(result.quality, ("blurry", "no_face", "ambiguous_faces", "invalid_landmarks"))
                    continue
                for crop in result.crops[:2]:
                    self.assertLess(self.model.predict(crop)["Closed"], .8)

    def test_true_closed_crops_retain_prolonged_closure_alert_after_blur(self):
        image = cv2.imread(str(ROOT / "tests/fixtures/eyes/closed_eye.jpg"))
        for params in STRESS_BLURS:
            with self.subTest(blur=params):
                probabilities = self.model.predict(apply_blur(image, params))
                self.assertGreaterEqual(probabilities["Closed"], .8)
                monitor = Monitor(self.config.monitor)
                for index in range(61):
                    status = monitor.update(Observation(index/30, probabilities, probabilities,
                                            {"yawn": 0., "no_yawn": 1.}))
                self.assertTrue(status.alert)
                self.assertIn("eyes_closed_too_long", status.reasons)


if __name__ == "__main__":
    unittest.main()
