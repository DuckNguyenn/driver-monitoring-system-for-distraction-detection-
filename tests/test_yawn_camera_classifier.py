"""Real-pixel regressions for missed camera yawns and smile negatives.

These fixtures are development evidence from one person. Full recorded video
is replayed separately with its capture timestamps; held-frame checks here
test the classifier/decision seam and do not represent video event accuracy.
"""
import json
import unittest
import cv2

from driver_monitor import Monitor, Observation
from driver_monitor.config import ROOT, load_config
from driver_monitor.models import Classifier, sha256
from driver_monitor.vision import Vision


@unittest.skipUnless((ROOT / "tests/fixtures/yawns/source.json").is_file(),
                     "Personal camera regression images are not distributed with the repository")
class YawnCameraClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "configs/camera_pc.yaml")
        cls.onnx = Classifier(cls.config.manifest, "yawn", "onnx")
        cls.torch = Classifier(cls.config.manifest, "yawn", "torch")
        fixtures = ROOT / "tests/fixtures/yawns"
        cls.samples = []
        for sample in json.loads((fixtures / "source.json").read_text(encoding="utf-8"))["samples"]:
            path = fixtures / sample["file"]
            if sha256(path) != sample["sha256"]:
                raise ValueError("Camera fixture checksum mismatch")
            face = Vision(cls.config).observe(cv2.imread(str(path)))
            if face.quality != "usable":
                raise ValueError(f"Fixture lost observation quality: {sample['file']}")
            cls.samples.append((sample, face.crops[2]))

    @classmethod
    def tearDownClass(cls):
        cls.onnx.close()
        cls.torch.close()

    def test_camera_yawns_reach_the_confirmation_probability(self):
        for sample, crop in self.samples:
            if sample["label"] == "yawn":
                with self.subTest(file=sample["file"]):
                    values = self.onnx.predict(crop)
                    self.assertGreaterEqual(values["yawn"], self.config.monitor.yawn_enter_probability, values)

    def test_sustained_camera_smile_and_neutral_faces_do_not_count(self):
        for sample, crop in self.samples:
            if sample["label"] != "no_yawn":
                continue
            with self.subTest(file=sample["file"]):
                monitor = Monitor(self.config.monitor)
                eye = {"Open": 1., "Closed": 0.}
                for frame in range(61):
                    status = monitor.update(Observation(frame / 30, eye, eye, self.onnx.predict(crop)))
                self.assertEqual(status.yawn_count, 0)
                self.assertFalse(status.alert)

    def test_torch_onnx_probability_parity_on_camera_crops(self):
        for sample, crop in self.samples:
            with self.subTest(file=sample["file"]):
                reference = self.torch.predict(crop)
                actual = self.onnx.predict(crop)
                self.assertEqual(max(reference, key=reference.get), max(actual, key=actual.get))
                self.assertAlmostEqual(reference["yawn"], actual["yawn"], delta=1e-5)


if __name__ == "__main__":
    unittest.main()
