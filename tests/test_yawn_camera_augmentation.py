"""Training augmentation must preserve validation/regression inputs and timing."""
import unittest
import numpy as np
from driver_monitor.models import prepare_rgb,read_manifest
from driver_monitor.config import ROOT
from tools.refine_yawn_camera import camera_feature_views,sample_camera_training


class YawnCameraAugmentationTests(unittest.TestCase):
    def setUp(self):
        self.crop=np.random.default_rng(4).integers(20,230,(320,235,3),dtype=np.uint8)
        self.spec=read_manifest(ROOT/'models/yawn_usb_refined/manifest.json')['classifiers']['yawn']

    def test_camera_noise_augmentation_is_reproducible_and_does_not_mutate_pixels(self):
        before=self.crop.copy()
        views=camera_feature_views(self.crop,self.spec,'train',True,seed=6)
        repeated=camera_feature_views(self.crop,self.spec,'train',True,seed=6)
        self.assertGreater(len(views),1)
        np.testing.assert_array_equal(self.crop,before)
        np.testing.assert_array_equal(views['original'],prepare_rgb(self.crop,self.spec))
        for name,image in views.items():
            np.testing.assert_array_equal(image,repeated[name])
            self.assertEqual(image.shape,(224,224,3))
            self.assertEqual(image.dtype,np.uint8)
        self.assertFalse(np.array_equal(views['noise_3'],views['original']))

    def test_validation_and_regression_never_receive_training_augmentation(self):
        for split in ('val','test','regression',None):
            with self.subTest(split=split):
                views=camera_feature_views(self.crop,self.spec,split,True,seed=8)
                self.assertEqual(list(views),['original'])

    def test_existing_prepare_remains_single_view_unless_augmentation_is_requested(self):
        self.assertEqual(list(camera_feature_views(self.crop,self.spec,'train',False)),['original'])

    def test_sampling_retains_each_augmentation_at_most_five_times_per_second(self):
        rows=[{'timestamp':i/10,'frame':i,'split':split,'label':'yawn','action':'first',
               'feature':i*2+j,'augmentation':variant}
              for split in ('train','val','regression') for i in range(7)
              for j,variant in enumerate(('original','noise_3'))]
        chosen=sample_camera_training(rows)
        self.assertEqual({r['split'] for r in chosen},{'train'})
        self.assertEqual({r['augmentation'] for r in chosen},{'original','noise_3'})
        for variant in ('original','noise_3'):
            times=[r['timestamp'] for r in chosen if r['augmentation']==variant]
            self.assertGreaterEqual(len(times),3)
            self.assertTrue(all(b-a>=.199999 for a,b in zip(times,times[1:])))
