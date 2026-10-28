"""The original-model recorder must preserve pixels, time and CSV alignment."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from driver_monitor.capture import Capture, Frame
from driver_monitor.models import prepare_rgb, read_manifest
from driver_monitor.config import ROOT
from driver_monitor.vision import VisionResult
from tools import test_original_model


class OriginalModelRecordingTests(unittest.TestCase):
    def test_raw_pixels_input_hashes_and_nonuniform_timestamps_replay_exactly(self):
        rng = np.random.default_rng(42)
        frames = [rng.integers(0, 256, (120, 160, 3), dtype=np.uint8) for _ in range(3)]
        original = [f.copy() for f in frames]
        source_times = [20., 20.073, 20.202]
        packets = [Frame(t, image, t, i*2) for i, (t, image) in enumerate(zip(source_times, frames))]
        capture = Mock(live=True, eof=False, error=None)
        def read():
            if packets:
                return packets.pop(0)
            capture.eof = True
            return None
        capture.read.side_effect = read
        model = Mock()
        model.predict.return_value = {"no_yawn": .1, "yawn": .9}
        vision = Mock()
        vision.observe.side_effect = [VisionResult("usable", (f[:20,:30], f[:20,:30], f[20:100,30:130]),
            ((0,0,30,20),(0,0,30,20),(30,20,130,100)),
            {"sharpness":25.,"eye_sharpness_min":8.}) for f in frames]
        with tempfile.TemporaryDirectory() as directory:
            args = ["--name","yawn","--source","0","--headless","--record","--output-dir",directory]
            with patch.object(test_original_model,"Capture",return_value=capture), \
                 patch.object(test_original_model,"Classifier",return_value=model), \
                 patch.object(test_original_model,"Vision",return_value=vision):
                self.assertEqual(test_original_model.main(args),0)
            video, = Path(directory).glob("*.avi")
            with video.with_suffix(".csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            sidecar=json.loads(video.with_suffix(".timestamps.json").read_text(encoding="utf-8"))
            metadata=json.loads(video.with_suffix(".metadata.json").read_text(encoding="utf-8"))
            np.testing.assert_allclose(sidecar["timestamps_seconds"],[0.,.073,.202])
            self.assertEqual([int(r["recording_frame"]) for r in rows],[0,1,2])
            self.assertEqual([int(r["frame"]) for r in rows],[0,2,4])
            self.assertTrue(all(int(r["face_crop_width"])==100 and int(r["face_crop_height"])==80 for r in rows))
            self.assertTrue(all([int(r[f"roi1_{k}"]) for k in ("x1", "y1", "x2", "y2")] == [30, 20, 130, 100]
                                for r in rows))
            self.assertFalse(metadata["ground_truth_reviewed"])
            self.assertEqual(metadata["codec"],"FFV1")
            self.assertEqual(metadata["model_origin"], "original")
            spec=read_manifest(ROOT/"models/manifest.json")["classifiers"]["yawn"]
            self.assertEqual(metadata["classes"], spec["classes"])
            self.assertEqual(metadata["preprocessing"], spec["preprocessing"])
            replay=Capture(video)
            try:
                for index, expected in enumerate(original):
                    packet=replay.read()
                    np.testing.assert_array_equal(packet.image,expected)
                    self.assertAlmostEqual(packet.timestamp,sidecar["timestamps_seconds"][index])
                    self.assertEqual(hashlib.sha256(packet.image.tobytes()).hexdigest(),sidecar["frame_sha256"][index])
                    rgb=prepare_rgb(packet.image[20:100,30:130],spec)
                    self.assertEqual(hashlib.sha256(rgb.tobytes()).hexdigest(),rows[index]["roi1_input_sha256"])
                self.assertIsNone(replay.read())
            finally:
                replay.close()
            for actual, expected in zip(frames,original):
                np.testing.assert_array_equal(actual,expected)
        capture.close.assert_called_once()
        model.close.assert_called_once()

    def test_runtime_eye_recording_uses_config_model_and_keeps_two_crop_streams_separate(self):
        frame = np.full((120, 160, 3), 80, np.uint8)
        frame[:20, :30] = [10, 35, 90]
        frame[:20, 40:70] = [120, 150, 170]
        left, right = frame[:20, :30], frame[:20, 40:70]
        capture = Mock(live=True, eof=False, error=None)
        packets = [Frame(20., frame, 20., 0)]
        def read():
            if packets:
                return packets.pop(0)
            capture.eof = True
            return None
        capture.read.side_effect = read
        model = Mock()
        # First predict is warm-up; independent probabilities follow for the two crops.
        model.predict.side_effect = [{"Closed": 0., "Open": 1.},
                                     {"Closed": .7, "Open": .3}, {"Closed": .02, "Open": .98}]
        vision = Mock()
        vision.observe.return_value = VisionResult("usable", (left, right, frame[20:100, 30:130]),
            ((0,0,30,20),(40,0,70,20),(30,20,130,100)),
            {"sharpness":25., "eye_sharpness_min":8., "face_min_side_pixels":85.}, confidence=.93)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest = read_manifest(ROOT / "models/manifest.json")
            manifest["classifiers"]["eye"]["artifacts"]["onnx"]["sha256"] = "a" * 64
            manifest_path = folder / "runtime_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            config_path = folder / "runtime.yaml"
            config_path.write_text("manifest: runtime_manifest.json\n", encoding="utf-8")
            args = ["--name", "eye", "--backend", "onnx", "--use-config-model", "--config", str(config_path),
                    "--source", "0", "--headless", "--record", "--output-dir", directory]
            with patch.object(test_original_model, "Capture", return_value=capture), \
                 patch.object(test_original_model, "Classifier", return_value=model) as constructor, \
                 patch.object(test_original_model, "Vision", return_value=vision):
                self.assertEqual(test_original_model.main(args), 0)
            self.assertEqual(constructor.call_args.args[:3], (manifest_path.resolve(), "eye", "onnx"))
            video, = folder.glob("*.avi")
            with video.with_suffix(".csv").open(encoding="utf-8") as stream:
                row, = list(csv.DictReader(stream))
            metadata = json.loads(video.with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["artifact_sha256"], "a" * 64)
            self.assertEqual(metadata["model_origin"], "runtime")
            self.assertEqual(metadata["roi_order"], "driver_anatomical_left_right")
            self.assertEqual(float(row["roi1_Closed"]), .7)
            self.assertEqual(float(row["roi2_Closed"]), .02)
            self.assertEqual(float(row["face_min_side_pixels"]), 85.)
            self.assertEqual(float(row["face_detector_confidence"]), .93)
            self.assertNotEqual(row["roi1_brightness_median"], row["roi2_brightness_median"])
            self.assertEqual((int(row["roi1_width"]), int(row["roi1_height"])), (30, 20))
            spec = manifest["classifiers"]["eye"]
            self.assertEqual(row["roi1_input_sha256"], hashlib.sha256(prepare_rgb(left, spec).tobytes()).hexdigest())
            self.assertEqual(row["roi2_input_sha256"], hashlib.sha256(prepare_rgb(right, spec).tobytes()).hexdigest())
            np.testing.assert_array_equal(model.predict.call_args_list[1].args[0], left)
            np.testing.assert_array_equal(model.predict.call_args_list[2].args[0], right)


if __name__=="__main__":
    unittest.main()
