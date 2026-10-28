"""Limited-distance development must not manufacture camera validation."""
import copy
import csv
import tempfile
import unittest
from pathlib import Path

from driver_monitor.config import ROOT
from driver_monitor.yawn_distance import FIELDS, read_distance_annotations
from tools.finetune_yawn_distance import options, selection_score, validation_passed


class NearMediumPolicyTests(unittest.TestCase):
    def test_two_training_clips_need_explicit_limited_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            videos = Path(directory)
            annotations = videos / 'annotations.csv'
            rows = []
            for distance in ('near', 'medium'):
                clip = videos / f'{distance}.avi'
                clip.write_bytes(distance.encode())
                for i, action in enumerate(('normal', 'yawn', 'smile')):
                    rows.append(dict(zip(FIELDS, (clip.name, 'p01', 'train_01', 'train', distance,
                        'indoor', i*2, i*2+1, 'yawn' if action == 'yawn' else 'no_yawn', action, 'true'))))
            with annotations.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader(); writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, 'Missing reviewed'):
                read_distance_annotations(annotations, videos)
            rows = read_distance_annotations(annotations, videos,
                active_distances=('near', 'medium'), required_splits=('train',))
            self.assertEqual({r['distance'] for r in rows}, {'near', 'medium'})
            self.assertEqual({r['split'] for r in rows}, {'train'})
            self.assertEqual({r['label'] for r in rows}, {'no_yawn', 'yawn'})
            with self.assertRaisesRegex(ValueError, 'Missing reviewed'):
                read_distance_annotations(annotations, videos, active_distances=('near', 'medium'))

    def test_static_selection_does_not_reward_camera_training_fit(self):
        static = {'macro_f1': .95, 'positive_samples': 40, 'negative_samples': 40,
                  'yawn_recall_at_070_including_unknown': .90, 'false_yawn_at_070': 0.,
                  'brier_score': .04}
        baseline = {'static/legacy': static,
            'static/smiles': {**static, 'positive_samples': 0},
            'static/genki': {**static, 'positive_samples': 0}}
        candidate = copy.deepcopy(baseline)
        candidate['camera/near'] = {'macro_f1': 0.}
        self.assertFalse(validation_passed(candidate, baseline, ('near', 'medium'), 'static_only'))
        score = selection_score(candidate, ('near', 'medium'), 'static_only')
        candidate['camera/near']['macro_f1'] = 1.
        self.assertEqual(score, selection_score(candidate, ('near', 'medium'), 'static_only'))
        candidate['static/legacy']['yawn_recall_at_070_including_unknown'] = .5
        self.assertIn('static_regression:static/legacy',
            validation_passed(candidate, baseline, ('near', 'medium'), 'static_only'))
        self.assertTrue(validation_passed({}, baseline, ('near', 'medium'), 'static_only'))
        with self.assertRaisesRegex(ValueError, 'static validation'):
            selection_score({'camera/near': {'macro_f1': 1.}}, ('near', 'medium'), 'static_only')

    def test_rigorous_recipe_remains_default_and_missing_far_is_rejected(self):
        o = options(ROOT / 'configs/yawn_distance_training.yaml')
        self.assertEqual(o['validation_mode'], 'camera')
        self.assertEqual(o['active_distances'], ('near', 'medium', 'far'))
        item = {'macro_f1': .99, 'positive_samples': 40, 'negative_samples': 40,
                'yawn_recall_at_070_including_unknown': .99, 'false_yawn_at_070': 0.}
        metrics = {f'camera/{d}': item for d in ('all', 'near', 'medium')}
        self.assertIn('insufficient_validation:camera/far', validation_passed(metrics, metrics))
        self.assertFalse(validation_passed(metrics, metrics, ('near', 'medium')))


if __name__ == '__main__':
    unittest.main()
