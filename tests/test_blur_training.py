"""Pixel, split and calibration contracts for blur refinement."""
import unittest

import numpy as np

from driver_monitor.blur import (apply_blur, calibrate_quality, exclude_split_duplicates,
                                 motion_kernel, training_blurs)
from driver_monitor.config import Config


class BlurTrainingTests(unittest.TestCase):
    def test_blurs_preserve_native_geometry_and_constant_brightness(self):
        image = np.full((23, 37, 3), 97, np.uint8)
        for params in training_blurs("train", "frame:both_eyes"):
            result = apply_blur(image, params)
            self.assertEqual(result.shape, image.shape)
            self.assertEqual(result.dtype, np.uint8)
            np.testing.assert_array_equal(result, image)
        np.testing.assert_array_equal(image, np.full_like(image, 97))

    def test_blur_actually_removes_edges_without_mutating_input(self):
        image = np.zeros((41, 41, 3), np.uint8)
        image[:, 20:] = 255
        original = image.copy()
        for params in ({"kind": "gaussian", "sigma": .8}, {"kind": "motion", "length": 5, "angle": 0}):
            blurred = apply_blur(image, params)
            self.assertTrue(np.any((blurred > 0) & (blurred < 255)))
            self.assertLess(float(np.square(np.diff(blurred.astype(float), axis=1)).sum()),
                            float(np.square(np.diff(image.astype(float), axis=1)).sum()))
        np.testing.assert_array_equal(image, original)

    def test_reproducible_train_only_variants_and_balanced_motion_kernel(self):
        self.assertEqual(training_blurs("train", "person/clip/frame", 7),
                         training_blurs("train", "person/clip/frame", 7))
        for split in ("val", "test", "regression"):
            self.assertEqual(training_blurs(split, "frame"), [])
        for angle in (-60, 0, 30, 90):
            self.assertAlmostEqual(float(motion_kernel(5, angle).sum()), 1, places=6)
        with self.assertRaises(ValueError):
            motion_kernel(4, 0)

    def test_holdout_image_excludes_every_training_variant(self):
        records = [dict(parent_id="a", split="train", sha256="same", label="Open", variant=v)
                   for v in ("base", "gaussian", "motion")]
        records.append(dict(parent_id="b", split="test", sha256="same", label="Open"))
        kept, excluded = exclude_split_duplicates(records)
        self.assertEqual(excluded, ["a"])
        self.assertEqual([r["parent_id"] for r in kept], ["b"])

    def test_photo_family_and_preprocessed_duplicate_checks(self):
        records = [dict(parent_id="a", split="train", sha256="1", label="Closed", source="cew", photo_family="8"),
                   dict(parent_id="b", split="val", sha256="2", label="Closed", source="cew", photo_family="8"),
                   dict(parent_id="c", split="train", sha256="3", label="Open", input_sha256="pixels"),
                   dict(parent_id="d", split="test", sha256="4", label="Open", input_sha256="pixels")]
        _, excluded = exclude_split_duplicates(records)
        self.assertEqual(excluded, ["a", "c"])
        records[-1]["label"] = "Closed"
        with self.assertRaisesRegex(ValueError, "conflicting labels"):
            exclude_split_duplicates(records)

    def calibration_inputs(self):
        rows, probabilities = {}, {}
        for kind, classes in (("eye", ("Closed", "Open")), ("yawn", ("no_yawn", "yawn"))):
            rows[kind] = []
            p = []
            for c, label in enumerate(classes):
                for i in range(10):
                    rows[kind].append(dict(feature=len(p), split="val", variant="base", label=label,
                        metrics=dict(sharpness=16. if i == 0 else 25., eye_sharpness_min=8.,
                                     brightness_median=60., eye_brightness_min=60., overexposed_ratio=0.)))
                    p.append([.95, .05] if c == 0 else [.05, .95])
            probabilities[kind] = np.asarray(p)
        return rows, probabilities

    def test_calibration_recovers_blur_without_fabricating_accuracy(self):
        rows, p = self.calibration_inputs()
        report = calibrate_quality(rows, p, p, Config(min_eye_sharpness=6), (20.,16.,12.), (6.,))
        self.assertEqual(report["selected"]["min_sharpness"], 16.)
        self.assertEqual(report["selected"]["additional_accepted_validation_samples"], 4)
        self.assertFalse(report["independent_camera_acceptance"])

    def test_calibration_rejects_false_closure_despite_fewer_unknowns(self):
        rows, p = self.calibration_inputs()
        candidate = {k:v.copy() for k,v in p.items()}
        candidate["eye"][10] = [.99, .01]
        report = calibrate_quality(rows, p, candidate, Config(min_eye_sharpness=6), (16.,), (6.,))
        self.assertIsNone(report["selected"])
        self.assertIn("false_confident_increase_eye_Closed", report["trials"][0]["rejection_reasons"])

    def test_calibration_rejects_holdout_and_keeps_darkness_guard(self):
        rows, p = self.calibration_inputs()
        rows["eye"][0]["split"] = "test"
        with self.assertRaisesRegex(ValueError, "only real base validation"):
            calibrate_quality(rows, p, p, Config(min_eye_sharpness=6))
        rows["eye"][0]["split"] = "val"
        rows["eye"][0]["metrics"]["brightness_median"] = 10
        report = calibrate_quality(rows, p, p, Config(min_eye_sharpness=6), (16.,), (6.,))
        self.assertEqual(report["selected"]["metrics"]["eye"]["blocked"], 1)

    def test_equal_global_errors_cannot_hide_a_new_camera_error(self):
        rows, p = self.calibration_inputs()
        for kind in rows:
            for i,r in enumerate(rows[kind]):
                r["group"] = "camera" if i % 2 == 0 else "static"
        rows["eye"][10]["metrics"]["sharpness"] = 25
        before = {k:v.copy() for k,v in p.items()}
        after = {k:v.copy() for k,v in p.items()}
        before["eye"][11] = [.99,.01]  # Existing static false closure.
        after["eye"][10] = [.99,.01]   # Replacing it with a camera false closure is rejected.
        result = calibrate_quality(rows,before,after,Config(min_eye_sharpness=6),(20.,),(6.,))
        self.assertIsNone(result["selected"])
        self.assertIn("source_false_confident_increase_eye_camera_Closed",result["trials"][0]["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
