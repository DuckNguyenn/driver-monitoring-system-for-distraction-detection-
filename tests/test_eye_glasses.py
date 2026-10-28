import unittest
from driver_monitor.eye_glasses import mrl_annotation,sample_mrl


class GlassesDatasetTests(unittest.TestCase):
    def test_published_field_order_keeps_glasses_and_eye_label_distinct(self):
        a=mrl_annotation('data/test/close eyes/s0018_03749_0_1_0_2_1_01.png')
        self.assertEqual((a['glasses'],a['label'],a['reflection'],a['lighting']),(True,'Closed',2,1))
        b=mrl_annotation('data/test/open eyes/s0018_03750_0_0_1_0_0_02.png')
        self.assertEqual((b['glasses'],b['label'],b['sensor']),(False,'Open','02'))

    def test_unannotated_or_invalid_images_are_not_given_guessed_labels(self):
        for name in ('Closed_01.jpg','s0018_03749_0_2_0_0_1_01.png','s0018_03749_0_1_0_3_1_01.png'):
            self.assertIsNone(mrl_annotation(name))

    def test_balanced_sampling_is_stable_under_archive_order_and_prediction_free(self):
        rows=[]
        for glasses in (0,1):
            for eye in (0,1):
                for subject in (1,2):
                    for frame in range(5):
                        rows.append(mrl_annotation(f'data/test/s{subject:04d}_{frame:05d}_0_{glasses}_{eye}_0_1_01.png'))
        a=sample_mrl(rows,4);b=sample_mrl(list(reversed(rows)),4)
        self.assertEqual(a,b)
        self.assertEqual(len(a),16)
        for glasses in (False,True):
            for label in ('Closed','Open'):
                selected=[r for r in a if r['glasses']==glasses and r['label']==label]
                self.assertEqual(len(selected),4)
                self.assertEqual({r['subject'] for r in selected},{'s0001','s0002'})


if __name__=='__main__':unittest.main()
