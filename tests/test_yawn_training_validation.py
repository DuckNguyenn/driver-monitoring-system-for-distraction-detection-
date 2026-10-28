"""Checkpoint selection must validate elapsed-time events, not isolated scores."""
import unittest
import numpy as np

from driver_monitor.core import MonitorConfig
from tools.refine_yawn_camera import camera_event_validation


class YawnTrainingValidationTests(unittest.TestCase):
    def replay(self, scores, rejected=()):
        rows = [{'timestamp':i/10,'feature':i,'split':'val',
            'quality':'blurry' if i in rejected else 'usable','track_changed':False} for i in range(len(scores))]
        probabilities = np.array([[1-p,p] for p in scores])
        labels = [{'start':0.,'end':len(scores)/10,'label':'yawn','split':'val'}]
        return camera_event_validation(rows,probabilities,labels,MonitorConfig())

    def test_a_continuous_event_can_pass_without_every_edge_frame_being_positive(self):
        result = self.replay([.01]*3+[.99]*18)
        self.assertTrue(result['passed'])
        self.assertEqual(result['yawn_hits'],1)

    def test_most_positive_frames_cannot_replace_a_continuous_second(self):
        scores = [.99]*21
        scores[8] = scores[16] = .01
        result = self.replay(scores)
        self.assertFalse(result['passed'])
        self.assertEqual(result['yawn_hits'],0)

    def test_quality_rejection_interrupts_confirmation(self):
        result = self.replay([.99]*21,rejected=(10,))
        self.assertFalse(result['passed'])

    def test_training_and_second_bout_scores_do_not_participate_in_selection(self):
        rows = [{'timestamp':i/10,'feature':i,'split':'val' if i<21 else 'regression',
            'quality':'usable','track_changed':False} for i in range(81)]
        values = np.array([[.01,.99] if i<21 or i>=60 else [.99,.01] for i in range(81)])
        intervals = [{'start':0.,'end':2.1,'label':'yawn','split':'val'},
            {'start':3.,'end':5.,'label':'no_yawn','split':'regression'},
            {'start':6.,'end':8.1,'label':'yawn','split':'regression'}]
        result = camera_event_validation(rows,values,intervals,MonitorConfig())
        self.assertTrue(result['passed'])
        self.assertEqual(result['expected_yawns'],1)
        self.assertEqual(len(result['confirmation_seconds']),1)
