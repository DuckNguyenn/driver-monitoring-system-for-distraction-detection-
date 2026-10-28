import unittest
import numpy as np
from driver_monitor.multiview_learning import augment_native,matrix_metrics,evaluate,validation_score


class MultiviewLearningTests(unittest.TestCase):
    def test_unknown_is_a_missed_positive_and_not_silently_removed(self):
        metric=matrix_metrics(['Closed','Closed','Open'],['Closed','UNKNOWN','Closed'],['Closed','Open'])
        self.assertEqual(metric['confusion_matrix'],[[1,0],[1,0]])
        self.assertEqual(metric['confusion_matrix_with_unknown'],[[1,0,1],[1,0,0]])
        self.assertEqual(metric['per_class']['Closed']['recall'],.5)
        self.assertEqual(metric['per_class']['Closed']['precision'],.5)

    def test_absent_class_does_not_claim_a_measured_recall(self):
        metric=matrix_metrics(['Open'],['Open'],['Closed','Open'])
        self.assertIsNone(metric['per_class']['Closed']['recall'])
        self.assertEqual(metric['per_class']['Closed']['support'],0)

    def test_validation_augmentation_is_a_pixel_preserving_copy(self):
        image=np.random.default_rng(1).integers(0,256,(27,35,3),dtype=np.uint8)
        transformed=augment_native(image,np.random.default_rng(2),False)
        np.testing.assert_array_equal(transformed,image)
        self.assertIsNot(transformed,image)

    def test_native_jitter_blur_keep_shape_dtype_and_do_not_mutate_original(self):
        image=np.random.default_rng(1).integers(0,256,(27,35,3),dtype=np.uint8);before=image.copy()
        for seed in range(25):
            augmented=augment_native(image,np.random.default_rng(seed),True)
            self.assertEqual(augmented.shape,image.shape);self.assertEqual(augmented.dtype,np.uint8)
        np.testing.assert_array_equal(before,image)

    def test_quality_and_low_confidence_remain_unknown_in_runtime_proxy(self):
        rows=[{'label':'Closed','quality':'blurry','domain':'camera','source':'heldout','resolution':'640'},
              {'label':'Open','quality':'usable','domain':'camera','source':'heldout','resolution':'640'}]
        metric=evaluate(rows,np.array([[.95,.05],[.4,.6]]),'eye')
        self.assertEqual(metric['accuracy'],1.)
        self.assertEqual(metric['confidence_and_quality_gate']['coverage'],0.)
        self.assertEqual(metric['confidence_and_quality_gate']['per_class']['Closed']['recall'],0.)

    def test_regressed_validation_cannot_become_qualified_by_training_fit(self):
        rows=[{'label':'Closed','quality':'usable','domain':'static','source':'legacy'},
              {'label':'Open','quality':'usable','domain':'static','source':'legacy'}]
        baseline=evaluate(rows,np.array([[.95,.05],[.05,.95]]),'eye')
        candidate=evaluate(rows,np.array([[.9,.1],[.8,.2]]),'eye')
        _,reasons=validation_score(candidate,baseline)
        self.assertTrue(reasons)


if __name__=='__main__':unittest.main()
