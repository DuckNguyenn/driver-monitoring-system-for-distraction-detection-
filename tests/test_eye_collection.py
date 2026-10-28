import unittest
import csv
import tempfile
from pathlib import Path
from driver_monitor.eye_collection import eye_intervals, reviewed_eye_rows


class EyeCollectionTests(unittest.TestCase):
    def test_irregular_source_clock_is_used_instead_of_nominal_avi_fps(self):
        times=[0.,.08,.16,.37,.45]
        changes=[dict(frame=1,eye1='Open',eye2='Open'),dict(frame=3,eye1='Closed',eye2='Open')]
        rows=eye_intervals(changes,times,4)
        self.assertEqual(rows[0]['start'],.08);self.assertEqual(rows[0]['end'],.37)
        self.assertEqual(rows[1]['start'],.37)
        self.assertTrue(all(row['reviewed'] for row in rows))

    def test_unlabeled_prefix_and_unreviewed_tail_are_not_filled(self):
        rows=eye_intervals([dict(frame=2,eye1='Unknown',eye2='Open')],[0.,.1,.2,.3,.4],3)
        self.assertEqual(rows[0]['start_frame'],2)
        self.assertEqual(rows[0]['end_frame_exclusive'],4)
        self.assertEqual(rows[0]['eye1'],'Unknown')
        self.assertEqual(eye_intervals([],[0.,.1],1),[])

    def test_out_of_order_or_unreviewed_boundaries_are_rejected(self):
        for changes in ([dict(frame=1,eye1='Open',eye2='Open'),dict(frame=0,eye1='Closed',eye2='Open')],
                        [dict(frame=2,eye1='Closed',eye2='Open')],
                        [dict(frame=1,eye1='Blink',eye2='Open')]):
            with self.assertRaises(ValueError):eye_intervals(changes,[0.,.1,.2],1)

    def test_reviewed_csv_uses_recorded_frame_intervals_and_rejects_metadata_drift(self):
        collection=dict(subject_id='p01',capture_group='glasses_test_01',split='test')
        rows=eye_intervals([dict(frame=1,eye1='Closed',eye2='Open')],[0.,.07,.21,.37],2)
        record={**rows[0],**collection}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'eyes.csv'
            def write(value):
                with path.open('w',encoding='utf-8',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(value));writer.writeheader();writer.writerow(value)
            write(record)
            parsed=reviewed_eye_rows(path,{'collection':collection},[0.,.07,.21,.37])
            self.assertEqual(parsed[0]['start_frame'],1);self.assertEqual(parsed[0]['end_frame_exclusive'],3)
            for change in ({'split':'train'},{'start':.10},{'end':.4},{'eye2':'Blink'}):
                write({**record,**change})
                with self.assertRaises(ValueError):reviewed_eye_rows(path,{'collection':collection},[0.,.07,.21,.37])

    def test_unreviewed_csv_rows_never_become_ground_truth(self):
        collection=dict(subject_id='p01',capture_group='g',split='test')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'eyes.csv'
            path.write_text('reviewed,eye1,eye2\nFalse,Closed,Closed\n',encoding='utf-8')
            self.assertEqual(reviewed_eye_rows(path,{'collection':collection},[0.,.1]),[])


if __name__=='__main__':unittest.main()
