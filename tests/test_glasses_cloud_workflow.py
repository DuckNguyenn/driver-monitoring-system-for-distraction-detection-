"""Exercise native crop packaging and notebook generation without GPU/camera/network."""
import ast
import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from driver_monitor.config import ROOT
from driver_monitor.models import read_manifest,prepare_rgb,sha256
from tools import build_glasses_bundle,prepare_glasses_cloud
from tools.kaggle_glasses_training import metrics


class GlassesCloudWorkflowTests(unittest.TestCase):
    def fixture(self,folder):
        root=Path(folder);model_dir=root/'models/base';model_dir.mkdir(parents=True)
        manifest=copy.deepcopy(read_manifest(ROOT/'models/yawn_camera_refined/manifest.json'))
        for name,spec in manifest['classifiers'].items():
            for backend,artifact in spec['artifacts'].items():
                file=model_dir/(name+'.'+backend);file.write_bytes((name+backend).encode())
                artifact.update(file=file.name,sha256=sha256(file))
        detector=model_dir/'yunet.onnx';detector.write_bytes(b'synthetic detector artifact')
        manifest['detector'].update(file=detector.name,sha256=sha256(detector))
        (model_dir/'manifest.json').write_text(json.dumps(manifest))
        config=root/'runtime.yaml';config.write_text('manifest: models/base/manifest.json\n')
        spec=manifest['classifiers']['eye'];seed=0
        def image():
            nonlocal seed
            seed+=1
            return np.random.default_rng(seed).integers(0,256,(24,36,3),dtype=np.uint8)
        archive=root/'.cache/mrl_glasses/kaggle/mrl-eye-dataset.zip';archive.parent.mkdir(parents=True)
        with zipfile.ZipFile(archive,'w') as zipped:
            for subject in ('s0001','s0002','s0019'):
                for glasses in (0,1):
                    for opened in (0,1):
                        _,raw=cv2.imencode('.png',image())
                        zipped.writestr(f'train/{subject}_{glasses*2+opened:04d}_0_{glasses}_{opened}_0_1_01.png',raw.tobytes())
        old=root/'kaggle_upload/multiview_20261013';old.mkdir(parents=True);records=[]
        for split in ('train','val','test'):
            for label in ('Closed','Open'):
                file=old/f'{split}_{label}.png';cv2.imwrite(str(file),image())
                records.append(dict(file=file.name,sha256=sha256(file),split=split,label=label,task='eye',source='legacy'))
        (old/'dataset.json').write_text(json.dumps({'records':records}))
        extra=root/'supplement';extra.mkdir();records=[]
        for split,person in (('train','p02'),('val','p03'),('test','p01')):
            for label in ('Closed','Open'):
                for index in range(20):
                    crop=image();file=extra/f'{split}_{label}_{index}.png';cv2.imwrite(str(file),crop)
                    records.append(dict(file=file.name,sha256=sha256(file),input_sha256=hashlib.sha256(prepare_rgb(crop,spec).tobytes()).hexdigest(),
                                        split=split,label=label,domain='rgb_rehearsal',subject=person,capture_group=person+'_01',
                                        glasses=True,new_glasses_camera=True,reviewed=True,source='synthetic_fixture',
                                        quality='blurry' if index==0 else 'usable',resolution='RGB_camera_native'))
        metadata=dict(kind='driver_monitor_eye_rgb_supplement',automatic_eye_labels=False,subject_split_verified=True,
                      runtime_spec=spec,records=records,sources=[{'source':'synthetic packaging test only'}])
        (extra/'dataset.json').write_text(json.dumps(metadata))
        (root/'driver_monitor').mkdir();(root/'tools').mkdir();(root/'notebooks').mkdir()
        for name in ('models.py','multiview_learning.py','glasses_training.py'):
            (root/'driver_monitor'/name).write_bytes((ROOT/'driver_monitor'/name).read_bytes())
        (root/'tools/kaggle_glasses_training.py').write_bytes((ROOT/'tools/kaggle_glasses_training.py').read_bytes())
        return root,config,extra

    def test_bundle_preserves_pixels_splits_quality_and_the_selected_yawn_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root,config,extra=self.fixture(directory);bundle=root/'new_bundle'
            with patch.object(build_glasses_bundle,'ROOT',root):
                build_glasses_bundle.main(['--config',str(config),'--rgb-supplement',str(extra),'--output-bundle',str(bundle)])
            data=json.loads((bundle/'dataset.json').read_text());locked=json.loads((bundle/'bundle.json').read_text())
            self.assertTrue(data['new_rgb_glasses_camera_present'])
            fresh=[r for r in data['records'] if r.get('new_glasses_camera')]
            self.assertEqual(len(fresh),120);self.assertEqual(sum(r['quality']=='blurry' for r in fresh),6)
            for row in fresh:
                crop=cv2.imread(str(bundle/row['file']))
                self.assertEqual(hashlib.sha256(prepare_rgb(crop,data['runtime_spec']).tobytes()).hexdigest(),row['input_sha256'])
            for file,checksum in locked['checksums'].items():self.assertEqual(sha256(bundle/file),checksum)
            exported=json.loads((bundle/'base_manifest.json').read_text())
            self.assertEqual(exported['classifiers']['yawn']['artifacts']['onnx']['file'],'../base/yawn.onnx')
            self.assertEqual(exported['detector']['file'],'../base/yunet.onnx')
            self.assertAlmostEqual(data['sampling_mass']['rgb_glasses'],.45)

    def test_incomplete_review_or_preprocessing_mismatch_cannot_start_a_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root,config,extra=self.fixture(directory);file=extra/'dataset.json';original=json.loads(file.read_text())
            for tag,change in (('incomplete',{'records':[r for r in original['records'] if r['split']=='test']}),
                               ('automatic',{'automatic_eye_labels':True}),
                               ('preproc',{'runtime_spec':dict(original['runtime_spec'],input_size=128)})):
                file.write_text(json.dumps({**original,**change}));output=root/tag
                with patch.object(build_glasses_bundle,'ROOT',root),self.assertRaises(ValueError):
                    build_glasses_bundle.main(['--config',str(config),'--rgb-supplement',str(extra),'--output-bundle',str(output)])
                self.assertFalse(output.exists())

    def test_fresh_glasses_metric_does_not_disappear_inside_old_rgb_average(self):
        rows=[dict(domain='rgb_rehearsal',new_glasses_camera=False,label='Open',source='legacy',quality='usable'),
              dict(domain='rgb_rehearsal',new_glasses_camera=True,label='Open',source='fresh',quality='usable')]
        result=metrics(rows,np.array([[.01,.99],[.99,.01]],np.float32))
        self.assertEqual(result['rgb_rehearsal']['accuracy'],1.)
        self.assertEqual(result['rgb_glasses']['accuracy'],0.)

    def test_new_notebook_has_rgb_guards_and_does_not_overwrite_completed_job_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'notebooks').mkdir();history=root/'kaggle_upload/glasses_cloud';history.mkdir(parents=True)
            completed=history/'latest.json';completed.write_text('{"status":"complete","notebook_id":"locked-original-run"}')
            archive=root/'bundle.zip'
            with zipfile.ZipFile(archive,'w') as zipped:
                zipped.writestr('bundle.json',json.dumps({'kind':'driver_monitor_glasses_adaptation'}))
                zipped.writestr('dataset.json',json.dumps({'new_rgb_glasses_camera_present':True}))
            with patch.object(prepare_glasses_cloud,'ROOT',root):prepare_glasses_cloud.main(['--archive',str(archive)])
            self.assertEqual(json.loads(completed.read_text())['notebook_id'],'locked-original-run')
            state=json.loads((history/'latest-prepared.json').read_text());self.assertTrue(state['new_rgb_glasses_camera_present'])
            nb=json.loads((root/'notebooks/eye_glasses_gpu.ipynb').read_text(encoding='utf-8'))
            text=''.join(''.join(cell['source']) for cell in nb['cells'])
            self.assertIn('RGB kính45%',text);self.assertNotIn('Hiện chưa có video RGB',text)
            self.assertIn('không tăng mắt mở bị khẳng định nhắm',text)
            for cell in nb['cells']:
                if cell['cell_type']=='code':ast.parse(''.join(cell['source']))


if __name__=='__main__':unittest.main()
