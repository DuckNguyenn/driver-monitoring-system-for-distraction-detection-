"""Resolution loss must happen before the shared resize, without holdout leakage."""
import csv
import os
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from driver_monitor.models import prepare_rgb, read_manifest, sha256
from driver_monitor.config import ROOT
os.environ.setdefault('YOLO_CONFIG_DIR',str(ROOT/'.cache/ultralytics'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
from driver_monitor.yawn_distance import (DistanceAugmentation, FIELDS, downsample_native,
    read_distance_annotations, training_rgb)


class YawnDistanceTrainingTests(unittest.TestCase):
    def setUp(self):
        self.crop = np.random.default_rng(6).integers(0, 256, (301, 217, 3), dtype=np.uint8)
        self.spec = read_manifest(ROOT / "models/yawn_usb_robust/manifest.json")["classifiers"]["yawn"]

    def test_resolution_loss_precedes_runtime_resize_and_keeps_source_intact(self):
        original = self.crop.copy()
        recipe = DistanceAugmentation(factors=(.5,), downsample_probability=1,
                                      gaussian_probability=0, motion_probability=0)
        rgb = training_rgb(self.crop, self.spec, "train", recipe, np.random.default_rng(2))
        expected = prepare_rgb(cv2.resize(self.crop, (108, 150), interpolation=cv2.INTER_AREA), self.spec)
        np.testing.assert_array_equal(rgb, expected)
        np.testing.assert_array_equal(self.crop, original)
        # Downsampling an already-prepared 224x224 input is a different transform.
        wrong = cv2.resize(cv2.resize(prepare_rgb(self.crop, self.spec), (112, 112),
                           interpolation=cv2.INTER_AREA), (224, 224))
        self.assertFalse(np.array_equal(rgb, wrong))

    def test_validation_test_and_regression_use_exact_runtime_pixels(self):
        recipe = DistanceAugmentation(downsample_probability=1, gaussian_probability=1, motion_probability=1)
        for split in ("val", "test", "regression"):
            np.testing.assert_array_equal(training_rgb(self.crop, self.spec, split, recipe,
                np.random.default_rng(2)), prepare_rgb(self.crop, self.spec))

    def test_random_augmentation_reproducible_and_keeps_small_crops(self):
        recipe = DistanceAugmentation(downsample_probability=1, gaussian_probability=1, motion_probability=1)
        np.testing.assert_array_equal(training_rgb(self.crop, self.spec, "train", recipe, np.random.default_rng(3)),
                                      training_rgb(self.crop, self.spec, "train", recipe, np.random.default_rng(3)))
        self.assertEqual(downsample_native(self.crop, .01).shape[:2], (33, 24))
        self.assertEqual(training_rgb(self.crop, self.spec, "train", recipe, np.random.default_rng(4)).shape, (224, 224, 3))

    def validate(self, updates=None, same_group=False, locked=False, split_mode="clip"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for i, split in enumerate(("train", "val")):
                clip = root / f"{split}.avi"
                clip.write_bytes(bytes([i]))
                for j, action in enumerate(("normal", "yawn", "smile")):
                    rows.append(dict(zip(FIELDS, (clip.name, "p01", "g0" if same_group else f"g{i}", split,
                        "near", "indoor", j * 2, j * 2 + 1, "yawn" if action == "yawn" else "no_yawn", action, "true"))))
            if updates:
                rows[0].update(updates)
            csv_path = root / "labels.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
            registry = {sha256(root / "train.avi"): "locked_check.json"} if locked else {}
            return read_distance_annotations(csv_path, root, split_mode, registry, require_coverage=False)

    def test_prompts_must_be_reviewed(self):
        with self.assertRaisesRegex(ValueError, "ground truth"):
            self.validate({"reviewed": "false"})

    def test_same_clip_or_capture_group_cannot_cross_splits(self):
        with self.assertRaisesRegex(ValueError, "capture_group leakage"):
            self.validate(same_group=True)
        with self.assertRaisesRegex(ValueError, "clip_id leakage"):
            self.validate({"clip_id": "val.avi"})

    def test_renamed_locked_video_cannot_train(self):
        with self.assertRaisesRegex(ValueError, "Locked diagnostic"):
            self.validate(locked=True)

    def test_same_subject_development_is_explicit_and_subject_mode_rejects_it(self):
        self.assertEqual(len(self.validate()), 6)
        with self.assertRaisesRegex(ValueError, "subject_id leakage"):
            self.validate(split_mode="subject")

    def test_classifier_fine_tuning_updates_conv_and_linear_preserves_backbone_bn_and_exports(self):
        import copy
        import torch
        from ultralytics import YOLO
        from driver_monitor.config import load_config
        from driver_monitor.models import artifact_path, prepare_tensor
        from tools.finetune_yawn_distance import configure_model, export_candidate, model_logits
        torch.set_num_threads(2); torch.manual_seed(42)
        config = load_config(ROOT / 'configs/camera_usb_robust.yaml')
        loaded = YOLO(str(artifact_path(config.manifest,self.spec['artifacts']['torch'])))
        trainable = configure_model(loaded.model)
        self.assertGreater(trainable, 2562)
        before = {k:v.clone() for k,v in loaded.model.state_dict().items()}
        x = torch.from_numpy(prepare_tensor(prepare_rgb(self.crop,self.spec),self.spec))
        optimizer = torch.optim.AdamW([p for p in loaded.model.parameters() if p.requires_grad],lr=1e-4)
        optimizer.zero_grad()
        loss = torch.nn.functional.cross_entropy(model_logits(loaded.model,x),torch.tensor([1]))
        loss.backward(); optimizer.step()
        changed = {k for k,v in loaded.model.state_dict().items() if not torch.equal(v,before[k])}
        head_prefix = f'model.{len(loaded.model.model)-1}.'
        self.assertTrue(changed)
        self.assertTrue(all(k.startswith(head_prefix) for k in changed))
        self.assertTrue(any('.conv.' in k for k in changed))
        self.assertTrue(any('.linear.' in k for k in changed))
        self.assertFalse(any('running_' in k or 'num_batches_tracked' in k for k in changed))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); native = output/'native.png'
            cv2.imwrite(str(native),self.crop)
            loaded.save(output/'best_yawn.pt')
            data = {'runtime_spec':copy.deepcopy(self.spec), 'augmentation':{}, 'camera_split_mode':'clip',
                'runtime_config_sha256':config.fingerprint(), 'records':[{'file':'native.png','split':'val'}]}
            report = {'dataset_sha256':'smoke_test_only','dataset_path':str(output)}
            export_candidate(output,config,data,report)
            import json
            parity = json.loads((output/'parity.json').read_text())
            self.assertTrue(parity['passed'])
            candidate = read_manifest(output/'manifest.json')
            self.assertEqual(candidate['classifiers']['yawn']['classes'],list(self.spec['classes']))
            self.assertEqual(candidate['classifiers']['yawn']['preprocessing'],self.spec['preprocessing'])
            active = read_manifest(config.manifest)
            self.assertEqual(candidate['classifiers']['eye']['artifacts']['onnx']['sha256'],
                             active['classifiers']['eye']['artifacts']['onnx']['sha256'])
            candidate_config = load_config(output/'runtime.yaml')
            from dataclasses import asdict
            original_settings, candidate_settings = asdict(config),asdict(candidate_config)
            original_settings.pop('manifest');candidate_settings.pop('manifest')
            self.assertEqual(candidate_settings,original_settings)
            self.assertNotEqual(candidate_config.fingerprint(),config.fingerprint())
