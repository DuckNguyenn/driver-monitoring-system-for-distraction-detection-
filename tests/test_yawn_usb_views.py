"""Multi-view contract regressions; screen fixtures are diagnostic, not raw-video acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from driver_monitor import Monitor, Observation
from driver_monitor.config import ROOT, load_config
from driver_monitor.models import Classifier, artifact_path, read_manifest, sha256


def candidate_manifest():
    source = ROOT / 'models/yawn_camera_refined/manifest.json'
    manifest = copy.deepcopy(read_manifest(source))
    manifest['schema_version'] = 2
    manifest['classifiers']['yawn']['inference_views'] = ['center', 'edge_pad_square']
    manifest['classifiers']['yawn']['view_aggregation'] = 'max_yawn'
    for spec in manifest['classifiers'].values():
        for artifact in spec['artifacts'].values():
            artifact['file'] = str(artifact_path(source, artifact))
    manifest['detector']['file'] = str(artifact_path(source, manifest['detector']))
    return manifest


class YawnViewContractTests(unittest.TestCase):
    def test_view_policy_changes_the_configuration_fingerprint_without_new_weights(self):
        config = load_config(ROOT/'configs/camera_pc.yaml')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'manifest.json';path.write_text(json.dumps(candidate_manifest()))
            candidate = load_config(ROOT/'configs/camera_pc.yaml', manifest=path)
            self.assertNotEqual(config.fingerprint(), candidate.fingerprint())

    def test_versioned_views_are_yawn_only_and_unknown_policies_are_rejected(self):
        manifest = candidate_manifest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            path.write_text(json.dumps(manifest))
            self.assertEqual(read_manifest(path)['schema_version'], 2)
            for broken in (
                dict(manifest, schema_version=1),
                dict(manifest, classifiers={**manifest['classifiers'], 'eye': {
                    **manifest['classifiers']['eye'], 'inference_views': ['center', 'edge_pad_square'],
                    'view_aggregation': 'max_yawn'}}),
                dict(manifest, classifiers={**manifest['classifiers'], 'yawn': {
                    **manifest['classifiers']['yawn'], 'view_aggregation': 'unknown'}}),
            ):
                path.write_text(json.dumps(broken))
                with self.assertRaises(ValueError): read_manifest(path)

    def test_existing_positive_evidence_and_class_names_survive_the_extra_view(self):
        for labels in (['no_yawn', 'yawn'], ['yawn', 'no_yawn']):
            model = Classifier.__new__(Classifier)
            model.spec = {'classes': labels, 'inference_views': ['center', 'edge_pad_square'], 'view_aggregation': 'max_yawn'}
            image = np.full((50, 30, 3), [5, 20, 80], np.uint8)
            before = image.copy()
            model._predict_one = lambda crop: {'yawn': .95 if crop.shape[0] != crop.shape[1] else .1,
                                               'no_yawn': .05 if crop.shape[0] != crop.shape[1] else .9}
            values = model.predict(image)
            self.assertAlmostEqual(values['yawn'], .95)
            self.assertAlmostEqual(sum(values.values()), 1.)
            np.testing.assert_array_equal(image, before)
            self.assertEqual(set(model.last_views), {'center', 'edge_pad_square'})

    @unittest.skipUnless((ROOT/'tests/fixtures/usb_yawn/source.json').is_file(), 'Local screen-derived diagnostic fixtures are not distributed')
    def test_screen_portrait_yawn_recovers_without_counting_the_neutral_frame(self):
        config = load_config(ROOT/'configs/camera_pc.yaml')
        fixtures = ROOT/'tests/fixtures/usb_yawn'
        records = json.loads((fixtures/'source.json').read_text(encoding='utf-8'))['samples']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'manifest.json';path.write_text(json.dumps(candidate_manifest()))
            model = Classifier(path,'yawn','onnx')
            reference = Classifier(config.manifest,'yawn','onnx')
            torch = Classifier(path,'yawn','torch')
            try:
                for record in records:
                    image = cv2.imread(str(fixtures/record['file']))
                    self.assertEqual(sha256(fixtures/record['file']), record['sha256'])
                    values = model.predict(image)
                    expected = record['label']=='yawn'
                    self.assertEqual(values['yawn']>=config.monitor.yawn_enter_probability, expected)
                    if expected: self.assertLess(reference.predict(image)['yawn'],config.monitor.yawn_enter_probability)
                    self.assertAlmostEqual(torch.predict(image)['yawn'],values['yawn'],delta=1e-5)
                    monitor = Monitor(config.monitor)
                    for i in range(21):
                        status = monitor.update(Observation(i/10,{'Open':1.,'Closed':0.}, {'Open':1.,'Closed':0.},values))
                    self.assertEqual(status.yawn_count,int(expected))
                    self.assertFalse(status.alert)
            finally:
                for item in (model,reference,torch):item.close()
