"""Real-model regressions: held smiles must not create yawns."""
import json
import unittest

import cv2

from driver_monitor import Monitor, Observation
from driver_monitor.config import ROOT, load_config
from driver_monitor.models import Classifier, sha256
from driver_monitor.vision import Vision


class SmileClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "configs/camera_pc.yaml")
        cls.model = Classifier(cls.config.manifest, "yawn", "onnx")

    @classmethod
    def tearDownClass(cls):
        cls.model.close()

    def hold(self, image):
        values = self.model.predict(image)
        monitor = Monitor(self.config.monitor)
        eye = {"Open": .99, "Closed": .01}
        for index in range(31):
            status = monitor.update(Observation(index / 15, eye, eye, values))
        return status

    @unittest.skipUnless((ROOT / "tests/fixtures/smiles/source.json").is_file(),
                         "Local face regression images are not distributed with the repository")
    def test_sustained_teeth_smiles_do_not_count_as_yawns(self):
        fixtures = ROOT / "tests/fixtures/smiles"
        for sample in json.loads((fixtures / "source.json").read_text())["samples"]:
            path = fixtures / sample["file"]
            with self.subTest(file=sample["file"]):
                self.assertEqual(sha256(path), sample["sha256"])
                status = self.hold(cv2.imread(str(path)))
                self.assertEqual(status.yawn_count, 0, f"Smile P(yawn)={status.yawn_raw_probability}")

    @unittest.skipUnless((ROOT / "kaggle_output/data/yawn_dataset/images/test/yawn__100__749ff8f0.jpg").is_file(),
                         "Local Kaggle image is not distributed with the repository")
    def test_true_yawn_still_confirms_an_event(self):
        path = ROOT / "kaggle_output/data/yawn_dataset/images/test/yawn__100__749ff8f0.jpg"
        result = Vision(self.config).observe(cv2.imread(str(path)))
        self.assertEqual(result.quality, "usable")
        self.assertEqual(self.hold(result.crops[2]).yawn_count, 1)


if __name__ == "__main__":
    unittest.main()
