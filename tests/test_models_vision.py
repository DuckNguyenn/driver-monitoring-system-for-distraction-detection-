from pathlib import Path
import tempfile
import unittest
import json
import types
from unittest.mock import patch
import cv2
import numpy as np
from PIL import Image
from driver_monitor.config import Config, ROOT
from driver_monitor.models import Classifier, artifact_path, prepare_rgb, prepare_tensor, read_manifest
from driver_monitor.vision import face_crops, Vision
from driver_monitor.capture import Capture
from driver_monitor.evaluation import classification_metrics


class ModelVisionTests(unittest.TestCase):
    def test_manifest_mapping_and_tampered_model_rejected(self):
        manifest = read_manifest(ROOT / "models/manifest.json")
        self.assertEqual(manifest["classifiers"]["eye"]["classes"], ["Closed", "Open"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.onnx"
            path.write_bytes(b"wrong")
            with self.assertRaises(ValueError):
                artifact_path(Path(directory) / "manifest.json", {"file": path.name, "sha256": "0" * 64})

    def test_preprocessing_matches_external_torchvision_reference(self):
        import os
        cache = ROOT / ".cache/ultralytics"
        cache.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(cache))
        from ultralytics.data.augment import classify_transforms
        spec = read_manifest(ROOT / "models/manifest.json")["classifiers"]["eye"]
        rng = np.random.default_rng(4)
        for shape in ((43, 79, 3), (121, 48, 3), (224, 224, 3), (479, 641, 3)):
            bgr = rng.integers(0, 256, shape, dtype=np.uint8)
            actual = prepare_tensor(prepare_rgb(bgr, spec), spec)[0]
            expected = classify_transforms(224)(Image.fromarray(bgr[:, :, ::-1])).numpy()
            np.testing.assert_allclose(actual, expected, atol=1e-7)

    def test_eye_crops_are_original_resolution_and_bounds_checked(self):
        config = Config()
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[:, :, 1] = np.arange(640, dtype=np.uint16)[None] % 256
        face = np.array([200, 100, 200, 220, 250, 160, 350, 160, 300, 190, 260, 240, 340, 240, .99])
        crops, boxes = face_crops(frame, face, config)
        self.assertEqual(crops[0].shape[:2], (60, 80))
        # YuNet's row stores the driver's right eye before the left eye.
        # Runtime's public order is left, right, face (anatomical side).
        np.testing.assert_array_equal(crops[0], frame[130:190, 310:390])
        np.testing.assert_array_equal(crops[1], frame[130:190, 210:290])
        with self.assertRaises(ValueError):
            face_crops(frame, np.zeros(15), config)

    @unittest.skipUnless((ROOT / "kaggle_output/data/yawn_dataset/images/test/yawn__100__749ff8f0.jpg").is_file(),
                         "Local Kaggle image is not distributed with the repository")
    def test_real_yunet_and_onnx_accept_a_cabin_sample(self):
        config = Config()
        image = cv2.imread(str(ROOT / "kaggle_output/data/yawn_dataset/images/test/yawn__100__749ff8f0.jpg"))
        result = Vision(config).observe(image)
        self.assertEqual(result.quality, "usable")
        model = Classifier(config.manifest, "yawn", "onnx")
        try:
            probabilities = model.predict(result.crops[2])
            self.assertEqual(set(probabilities), {"no_yawn", "yawn"})
            self.assertAlmostEqual(sum(probabilities.values()), 1.)
        finally:
            model.close()

    @unittest.skipUnless((ROOT / "kaggle_output/data/yawn_dataset/images/test/yawn__100__749ff8f0.jpg").is_file(),
                         "Local Kaggle image is not distributed with the repository")
    def test_brief_face_loss_does_not_invent_a_new_driver(self):
        config = Config()
        image = cv2.imread(str(ROOT / "kaggle_output/data/yawn_dataset/images/test/yawn__100__749ff8f0.jpg"))
        vision = Vision(config)
        self.assertTrue(vision.observe(image).track_changed)
        self.assertEqual(vision.observe(np.zeros_like(image)).quality, "no_face")
        self.assertFalse(vision.observe(image).track_changed)

    def test_video_reader_uses_media_time_and_reaches_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "video.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 15, (64, 48))
            for _ in range(15):
                writer.write(np.full((48, 64, 3), 70, np.uint8))
            writer.release()
            capture = Capture(path)
            try:
                packets = [capture.read() for _ in range(15)]
                self.assertAlmostEqual(packets[-1].timestamp, 14 / 15, places=3)
                self.assertIsNone(capture.read())
                self.assertTrue(capture.eof)
            finally:
                capture.close()

    def test_unknown_predictions_count_as_missed_not_success(self):
        metrics = classification_metrics(["a", "a", "b"], ["a", "UNKNOWN", "b"], ["a", "b"])
        self.assertEqual(metrics["per_class"]["a"]["recall"], .5)
        self.assertEqual(metrics["unknown_samples"], 1)

    def test_recording_sidecar_preserves_capture_gaps_and_rejects_wrong_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recording.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (64, 48))
            for _ in range(3):
                writer.write(np.full((48, 64, 3), 70, np.uint8))
            writer.release()
            sidecar = path.with_suffix(".timestamps.json")
            for times in ([0, .1, .5], [0, .1, .5, .6]):
                sidecar.write_text(json.dumps({"timestamps_seconds": times}))
                capture = Capture(path)
                try:
                    self.assertAlmostEqual(capture.read().timestamp, 0)
                    self.assertAlmostEqual(capture.read().timestamp, .1)
                    self.assertAlmostEqual(capture.read().timestamp, .5)
                    if len(times) == 3:
                        self.assertIsNone(capture.read())
                    else:
                        with self.assertRaises(ValueError):
                            capture.read()
                finally:
                    capture.close()

    def test_rknn_receives_rgb_uint8_without_double_normalization(self):
        class FakeRKNN:
            def load_rknn(self, path): return 0
            def init_runtime(self): return 0
            def inference(self, inputs, data_format):
                self.input, self.data_format = inputs[0], data_format
                return [np.array([[.2, .8]], np.float32)]
            def release(self): pass
        api = types.ModuleType("rknnlite.api")
        api.RKNNLite = FakeRKNN
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model_path = directory / "eye.rknn"
            model_path.write_bytes(b"test artifact")
            from driver_monitor.models import sha256
            manifest = read_manifest(ROOT / "models/manifest.json")
            manifest["classifiers"]["eye"]["artifacts"]["rknn"] = {"file": model_path.name, "sha256": sha256(model_path), "target_platform": "rk3576", "toolkit_version": "2.3.2"}
            manifest_path = directory / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            with patch.dict("sys.modules", {"rknnlite.api": api}), patch("platform.machine", return_value="aarch64"), patch("importlib.metadata.version", return_value="2.3.2"):
                model = Classifier(manifest_path, "eye", "rknn")
                try:
                    values = model.predict(np.full((32, 64, 3), [5, 7, 9], np.uint8))
                    self.assertEqual(model.model.input.dtype, np.uint8)
                    self.assertEqual(model.model.input.shape, (1, 224, 224, 3))
                    np.testing.assert_array_equal(model.model.input[0, 0, 0], [9, 7, 5])
                    self.assertEqual(model.model.data_format, ["nhwc"])
                    self.assertEqual(max(values, key=values.get), "Open")
                finally:
                    model.close()
