import unittest
import numpy as np
from driver_monitor.glasses_training import subject_split,validate_subjects,sampler_weights,augment_glasses,glasses_selection,validate_rgb_subjects
from driver_monitor.multiview_learning import evaluate


class GlassesTrainingTests(unittest.TestCase):
    def test_subjects_cannot_cross_finetuning_split_boundaries(self):
        rows=[]
        for subject in ('s0001','s0014','s0036'):
            for glasses in (False,True):
                for label in ('Closed','Open'):
                    rows.append(dict(domain='mrl',subject=subject,split=subject_split(subject),glasses=glasses,label=label))
        validate_subjects(rows)
        with self.assertRaisesRegex(ValueError,'subject leakage'):
            validate_subjects(rows+[dict(rows[0],split='test')])

    def test_sampling_mass_preserves_rgb_and_balances_each_class(self):
        rows=[]
        for domain,glasses,size in (('rgb_rehearsal',None,20),('mrl',False,4),('mrl',True,8)):
            for label in ('Closed','Open'):
                rows.extend(dict(domain=domain,glasses=glasses,label=label) for _ in range(size))
        weights=sampler_weights(rows)
        self.assertAlmostEqual(weights.sum(),1.)
        for domain,glasses,total in (('rgb_rehearsal',None,.55),('mrl',False,.15),('mrl',True,.30)):
            for label in ('Closed','Open'):
                self.assertAlmostEqual(sum(w for r,w in zip(rows,weights) if (r['domain'],r['glasses'],r['label'])==(domain,glasses,label)),total/2)

    def test_validation_images_are_never_augmented(self):
        image=np.random.default_rng(1).integers(0,256,(32,48,3),dtype=np.uint8)
        actual=augment_glasses(image,np.random.default_rng(2),False)
        np.testing.assert_array_equal(actual,image)
        self.assertIsNot(actual,image)

    def test_adding_rgb_glasses_does_not_double_total_rgb_mass(self):
        rows=[dict(domain='rgb_rehearsal',glasses=g,label=label) for g in (None,True) for label in ('Closed','Open')]
        rows += [dict(domain='mrl',glasses=g,label=label) for g in (False,True) for label in ('Closed','Open')]
        weights=sampler_weights(rows)
        self.assertAlmostEqual(weights.sum(),1.)
        self.assertAlmostEqual(sum(w for r,w in zip(rows,weights) if r['domain']=='rgb_rehearsal'),.55)

    def test_improving_glasses_does_not_qualify_rgb_regression(self):
        rows=[dict(label='Closed',quality='usable',domain='static',source='fixture'),
              dict(label='Open',quality='usable',domain='static',source='fixture')]
        good=evaluate(rows,np.array([[.95,.05],[.05,.95]]),'eye')
        bad=evaluate(rows,np.array([[.95,.05],[.95,.05]]),'eye')
        baseline=dict(rgb_rehearsal=good,mrl_no_glasses=good,mrl_glasses=bad)
        candidate=dict(rgb_rehearsal=bad,mrl_no_glasses=good,mrl_glasses=good)
        _,reasons=glasses_selection(candidate,baseline)
        self.assertIn('F1_regression:rgb_rehearsal',reasons)
        self.assertIn('RGB_confident_recall_regression:Open',reasons)

    def test_new_rgb_glasses_sampling_has_its_own_mass_without_hiding_baseline(self):
        rows=[]
        for domain,glasses,fresh in (('rgb_rehearsal',True,True),('rgb_rehearsal',None,False),('mrl',True,False),('mrl',False,False)):
            for label in ('Closed','Open'):
                rows.extend(dict(domain=domain,glasses=glasses,new_glasses_camera=fresh,label=label) for _ in range(3))
        weights=sampler_weights(rows)
        self.assertAlmostEqual(weights.sum(),1.)
        self.assertAlmostEqual(sum(w for r,w in zip(rows,weights) if r['new_glasses_camera']),.45)
        self.assertAlmostEqual(sum(w for r,w in zip(rows,weights) if r['domain']=='rgb_rehearsal' and not r['new_glasses_camera']),.25)

    def test_reviewed_rgb_subjects_and_groups_cannot_cross_splits(self):
        rows=[]
        for split,person in (('train','p02'),('val','p03'),('test','p01')):
            for label in ('Closed','Open'):
                rows.append(dict(domain='rgb_rehearsal',glasses=True,new_glasses_camera=True,reviewed=True,
                                 subject=person,capture_group=person+'_01',split=split,label=label))
        validate_rgb_subjects(rows,require_complete=True,minimum_per_class=1)
        for change in ({'subject':'p01'},{'capture_group':'p01_01'},{'reviewed':False}):
            bad=[dict(r,**change) if r['split']=='train' else r for r in rows]
            with self.assertRaises(ValueError):validate_rgb_subjects(bad,require_complete=True,minimum_per_class=1)
        with self.assertRaisesRegex(ValueError,'Missing reviewed RGB'):
            validate_rgb_subjects([r for r in rows if r['split']=='test'],require_complete=True,minimum_per_class=1)

    def test_selection_cannot_ignore_real_rgb_glasses_regression(self):
        rows=[dict(label='Closed',quality='usable',domain='rgb_rehearsal',source='fixture'),
              dict(label='Open',quality='usable',domain='rgb_rehearsal',source='fixture')]*20
        good=evaluate(rows,np.array([[.95,.05],[.05,.95]]*20),'eye')
        bad=evaluate(rows,np.array([[.95,.05],[.95,.05]]*20),'eye')
        baseline=dict(rgb_rehearsal=good,mrl_no_glasses=good,mrl_glasses=bad,rgb_glasses=good)
        candidate=dict(rgb_rehearsal=good,mrl_no_glasses=good,mrl_glasses=good,rgb_glasses=bad)
        _,reasons=glasses_selection(candidate,baseline)
        self.assertIn('RGB_glasses_F1_gain_below_2pp',reasons)
        self.assertIn('RGB_glasses_confident_false_closed_increased',reasons)


if __name__=='__main__':unittest.main()
