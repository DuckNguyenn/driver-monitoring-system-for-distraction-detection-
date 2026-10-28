"""Low-angle development pixels; sensor-domain acceptance still needs live data."""
import hashlib
import json
import unittest
import cv2
import numpy as np
from driver_monitor import Monitor,Observation
from driver_monitor.config import ROOT,load_config
from driver_monitor.models import Classifier,prepare_rgb,read_manifest,sha256


@unittest.skipUnless((ROOT/'tests/fixtures/usb_low_angle/source.json').is_file(),
    'Personal low-angle camera development fixtures are not distributed')
class UsbRobustClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=load_config(ROOT/'configs/camera_usb_robust.yaml')
        cls.model=Classifier(cls.config.manifest,'yawn','onnx')
        cls.torch=Classifier(cls.config.manifest,'yawn','torch')
        cls.samples=[]
        root=ROOT/'tests/fixtures/usb_low_angle'
        for row in json.loads((root/'source.json').read_text())['samples']:
            path=root/row['file']
            if sha256(path)!=row['sha256']:raise ValueError('Low-angle fixture changed')
            image=cv2.imread(str(path))
            rgb=prepare_rgb(image,cls.model.spec)
            if hashlib.sha256(rgb.tobytes()).hexdigest()!=row['input_sha256']:
                raise ValueError('Low-angle preprocessing changed')
            cls.samples.append((row,image))

    @classmethod
    def tearDownClass(cls):
        cls.model.close();cls.torch.close()

    def test_reviewed_low_angle_yawns_reach_the_existing_threshold(self):
        for row,image in self.samples:
            if row['label']!='yawn':continue
            with self.subTest(action=row['action']):
                self.assertGreaterEqual(self.model.predict(image)['yawn'],self.config.monitor.yawn_enter_probability)

    def test_relaxed_mouth_and_teeth_smile_do_not_confirm_a_yawn(self):
        for row,image in self.samples:
            if row['label']!='no_yawn':continue
            values=self.model.predict(image);monitor=Monitor(self.config.monitor)
            for i in range(31):status=monitor.update(Observation(i/10,yawn=values))
            with self.subTest(action=row['action']):
                self.assertEqual(status.yawn_count,0)
                self.assertFalse(status.alert)

    def test_small_sensor_noise_keeps_reviewed_positive_classification(self):
        for row,image in self.samples:
            if row['label']!='yawn':continue
            for seed in range(3):
                noise=np.random.default_rng(seed).normal(0,3,image.shape)
                noisy=np.clip(np.rint(image.astype(float)+noise),0,255).astype(np.uint8)
                with self.subTest(action=row['action'],seed=seed):
                    self.assertGreaterEqual(self.model.predict(noisy)['yawn'],self.config.monitor.yawn_enter_probability)

    def test_torch_onnx_match_and_eye_policy_are_unchanged(self):
        for row,image in self.samples:
            self.assertAlmostEqual(self.model.predict(image)['yawn'],self.torch.predict(image)['yawn'],delta=1e-5)
        base=load_config(ROOT/'configs/camera_usb_refined.yaml')
        self.assertEqual(self.config.monitor,base.monitor)
        old=read_manifest(base.manifest)['classifiers']['eye']['artifacts']['onnx']['sha256']
        new=read_manifest(self.config.manifest)['classifiers']['eye']['artifacts']['onnx']['sha256']
        self.assertEqual(old,new)
