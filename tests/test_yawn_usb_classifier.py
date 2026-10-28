"""Known USB-domain pixel regressions, not independent event accuracy."""
import hashlib
import json
import unittest

import cv2

from driver_monitor import Monitor, Observation
from driver_monitor.config import ROOT, load_config
from driver_monitor.models import Classifier, read_manifest, prepare_rgb, sha256


@unittest.skipUnless((ROOT/'tests/fixtures/usb_camera/source.json').is_file(),
    'Personal USB-camera development fixtures are not distributed')
class UsbYawnClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT/'configs/camera_usb_refined.yaml')
        cls.manifest = read_manifest(cls.config.manifest)
        cls.onnx = Classifier(cls.config.manifest,'yawn','onnx')
        cls.torch = Classifier(cls.config.manifest,'yawn','torch')
        root = ROOT/'tests/fixtures/usb_camera'
        cls.samples = []
        for row in json.loads((root/'source.json').read_text(encoding='utf-8'))['samples']:
            path = root/row['file']
            if sha256(path)!=row['sha256']:
                raise ValueError('USB development fixture changed')
            image = cv2.imread(str(path))
            rgb = prepare_rgb(image,cls.manifest['classifiers']['yawn'])
            if hashlib.sha256(rgb.tobytes()).hexdigest()!=row['input_sha256']:
                raise ValueError('USB regression preprocessing changed')
            cls.samples.append((row,image))

    @classmethod
    def tearDownClass(cls):
        cls.onnx.close()
        cls.torch.close()

    def test_reviewed_usb_yawn_crops_reach_the_existing_confirmation_threshold(self):
        for row,image in self.samples:
            if row['label']!='yawn':continue
            with self.subTest(action=row['action']):
                self.assertGreaterEqual(self.onnx.predict(image)['yawn'],self.config.monitor.yawn_enter_probability)

    def test_usb_neutral_and_teeth_smile_do_not_confirm_a_yawn(self):
        for row,image in self.samples:
            if row['label']!='no_yawn':continue
            with self.subTest(action=row['action']):
                values = self.onnx.predict(image)
                monitor = Monitor(self.config.monitor)
                for i in range(31):
                    status = monitor.update(Observation(i/10,{'Open':1.,'Closed':0.},
                        {'Open':1.,'Closed':0.},values))
                self.assertEqual(status.yawn_count,0)
                self.assertFalse(status.alert)

    def test_torch_and_onnx_match_on_usb_crops(self):
        for row,image in self.samples:
            with self.subTest(action=row['action']):
                self.assertAlmostEqual(self.torch.predict(image)['yawn'],self.onnx.predict(image)['yawn'],delta=1e-5)

    def test_eye_model_and_temporal_policy_remain_the_pc_baseline(self):
        base = load_config(ROOT/'configs/camera_pc.yaml')
        baseline = read_manifest(base.manifest)
        self.assertEqual(base.monitor,self.config.monitor)
        self.assertEqual(baseline['classifiers']['eye']['artifacts']['onnx']['sha256'],
            self.manifest['classifiers']['eye']['artifacts']['onnx']['sha256'])
        self.assertEqual(baseline['classifiers']['yawn']['preprocessing'],self.manifest['classifiers']['yawn']['preprocessing'])
