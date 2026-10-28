import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
import cv2
import numpy as np
from driver_monitor.config import ROOT,load_config
from driver_monitor.models import read_manifest,prepare_rgb,sha256
from tools.evaluate_eye_glasses_rgb import automatic_guesses,checked_dataset


class RGBGlassesEvaluationTests(unittest.TestCase):
    def test_single_eye_truth_is_scored_independently_and_unknown_is_not_false_open(self):
        rows=[{'frame':0,'eye_index':0},{'frame':0,'eye_index':1},{'frame':1,'eye_index':0},{'frame':2,'eye_index':1}]
        observation={'quality':'usable','eye_quality':'usable','left_eye':{'Closed':.99,'Open':.01},'right_eye':{'Closed':.01,'Open':.99}}
        records=[{'observation':observation},{'observation':dict(observation,eye_quality='eye_model_changed')},
                 {'observation':dict(observation,right_eye={'Closed':.6,'Open':.4})}]
        self.assertEqual(automatic_guesses(rows,records,.8),['Closed','Open','UNKNOWN','UNKNOWN'])
        with self.assertRaises(ValueError):automatic_guesses([{'frame':3,'eye_index':0}],records,.8)
        with self.assertRaises(ValueError):automatic_guesses([{'frame':0,'eye_index':-1}],records,.8)

    def test_evaluation_requires_reviewed_provenance_and_exact_input_pixels(self):
        config=load_config(ROOT/'configs/camera_pc.yaml')
        spec=read_manifest(config.manifest)['classifiers']['eye']
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);image=np.full((24,36,3),99,np.uint8);file=root/'eye.png';cv2.imwrite(str(file),image)
            row=dict(file=file.name,sha256=sha256(file),input_sha256=hashlib.sha256(prepare_rgb(image,spec).tobytes()).hexdigest(),
                     domain='rgb_rehearsal',new_glasses_camera=True,glasses=True,reviewed=True,subject='p01',capture_group='g01',
                     split='test',label='Open',frame=0,eye_index=0,source='synthetic_evaluation_fixture',quality='usable')
            data=dict(kind='driver_monitor_eye_rgb_supplement',automatic_eye_labels=False,runtime_spec=spec,records=[row])
            metadata=root/'dataset.json';metadata.write_text(json.dumps(data))
            _,rows=checked_dataset(root,config,'test');self.assertEqual(len(rows),1)
            metadata.write_text(json.dumps({**data,'automatic_eye_labels':True}))
            with self.assertRaises(ValueError):checked_dataset(root,config,'test')
            metadata.write_text(json.dumps(data));cv2.imwrite(str(file),np.full((24,36,3),100,np.uint8))
            with self.assertRaisesRegex(ValueError,'checksum'):checked_dataset(root,config,'test')


if __name__=='__main__':unittest.main()
