"""Exercise recording/review, native crop preparation and the real fitting loop."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from driver_monitor.config import ROOT, load_config
from driver_monitor.models import prepare_rgb, read_manifest, sha256
from driver_monitor.vision import VisionResult
from driver_monitor.yawn_distance import FIELDS, verify_prepared_dataset
from tools import record_yawn_check
from tools.annotate_yawn_distance import append_reviewed
from tools.finetune_yawn_distance import options, prepare, train


class YawnDistanceWorkflowTests(unittest.TestCase):
    def test_undersized_face_delays_recording_and_saves_only_clean_ready_frames(self):
        frames = [np.full((120,160,3),i*40,np.uint8) for i in range(4)]
        camera = Mock();camera.isOpened.return_value = True
        camera.read.side_effect = [(True,f) for f in frames]
        guide = Mock();guide.target = 100
        guide.inspect.side_effect = [(False,'MOVE CLOSER'),(True,'SIZE OK'),(True,'SIZE OK')]
        with tempfile.TemporaryDirectory() as directory:
            args = ['record_yawn_check.py','--guide-face-size','--output-dir',directory,
                '--config',str(ROOT/'configs/camera_usb_robust.yaml')]
            with patch('sys.argv',args),patch.object(record_yawn_check,'FaceSizeGuide',return_value=guide), \
                patch.object(record_yawn_check.cv2,'VideoCapture',return_value=camera), \
                patch.object(record_yawn_check.time,'monotonic',side_effect=[0.,5.1,5.5,10.2,10.3]), \
                patch.object(record_yawn_check.cv2,'imshow'),patch.object(record_yawn_check.cv2,'waitKey',side_effect=[-1,-1,-1,ord('q')]), \
                patch.object(record_yawn_check.cv2,'destroyAllWindows'):
                record_yawn_check.main()
            video, = Path(directory).glob('*.avi')
            sidecar = json.loads(video.with_suffix('.timestamps.json').read_text())
            np.testing.assert_allclose(sidecar['timestamps_seconds'],[0.,.1])
            self.assertEqual(sidecar['frame_sha256'],[hashlib.sha256(f.tobytes()).hexdigest() for f in frames[2:]])
            protocol = json.loads(video.with_suffix('.protocol.json').read_text())
            self.assertTrue(protocol['face_size_guide']['enabled'])
            self.assertEqual(protocol['collection']['runtime_config_sha256'],load_config(ROOT/'configs/camera_usb_robust.yaml').fingerprint())

    def test_new_distance_protocol_records_metadata_without_automatic_labels(self):
        image = np.random.default_rng(5).integers(0,256,(120,160,3),dtype=np.uint8)
        camera = Mock(); camera.isOpened.return_value = True
        camera.read.return_value = (True,image)
        with tempfile.TemporaryDirectory() as directory:
            args = ['record_yawn_check.py','--output-dir',directory,'--config',str(ROOT/'configs/camera_usb_robust.yaml'),
                '--distance','medium','--subject-id','p01','--capture-group','p01_train_01','--split','train']
            with patch('sys.argv',args), patch.object(record_yawn_check.cv2,'VideoCapture',return_value=camera), \
                patch.object(record_yawn_check.time,'monotonic',side_effect=[0.,5.1,53.2]), \
                patch.object(record_yawn_check.cv2,'imshow'),patch.object(record_yawn_check.cv2,'waitKey',return_value=-1), \
                patch.object(record_yawn_check.cv2,'destroyAllWindows'):
                record_yawn_check.main()
            video, = Path(directory).glob('*.avi')
            protocol = json.loads(video.with_suffix('.protocol.json').read_text())
            config = load_config(ROOT/'configs/camera_usb_robust.yaml')
            self.assertEqual(protocol['collection']['runtime_config_sha256'],config.fingerprint())
            self.assertEqual(protocol['collection']['distance'],'medium')
            self.assertEqual(protocol['phases'][-1][1],48)
            self.assertFalse(protocol['ground_truth_reviewed'])
            self.assertTrue(protocol['complete'])
            self.assertEqual(protocol['frames'],1)
            with video.with_suffix('.annotations.template.csv').open() as stream:
                self.assertEqual(len(list(csv.reader(stream))),1)  # no prompt labels

    def test_manual_reviews_append_and_reject_duplicate_clip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'labels.csv'
            row = dict(zip(FIELDS,('first.avi','p01','g1','train','near','day',0,1,'no_yawn','normal','true')))
            append_reviewed(path,[row])
            append_reviewed(path,[{**row,'clip_id':'second.avi'}])
            with path.open() as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),2)
            with self.assertRaisesRegex(ValueError,'already annotated'):
                append_reviewed(path,[row])

    def test_prepare_then_real_train_excludes_unknown_from_optimization_but_counts_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); videos = root/'videos'; videos.mkdir()
            o = options(ROOT/'configs/yawn_distance_training.yaml')
            o.update(videos=videos, annotations=root/'annotations.csv',dataset=root/'dataset',
                output=root/'candidate',static_train_per_group=1,static_val_per_group=1,epochs=1)
            static_records=[]
            for index,(split,label) in enumerate((s,l) for s in ('train','val') for l in ('no_yawn','yawn')):
                image=np.random.default_rng(100+index).integers(0,256,(120,160,3),dtype=np.uint8)
                path=root/f'static_{split}_{label}.png'
                self.assertTrue(cv2.imwrite(str(path),image))
                static_records.append(dict(path=str(path),sha256=sha256(path),feature=index,
                    variant='face',source='legacy',split=split,label=label))
            o['retained_static_records']=root/'static_records.json'
            o['retained_static_records'].write_text(json.dumps({'records':static_records}))
            config = load_config(o['runtime_config'])
            rows = []
            crops = []
            for index,(split,distance) in enumerate((s,d) for s in ('train','val') for d in ('near','medium','far')):
                path = videos/f'{split}_{distance}.avi'
                writer = cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'FFV1'),30.,(160,120))
                self.assertTrue(writer.isOpened())
                rng = np.random.default_rng(index)
                frames = [rng.integers(0,256,(120,160,3),dtype=np.uint8) for _ in range(6)]
                for frame in frames:writer.write(frame)
                writer.release()
                path.with_suffix('.timestamps.json').write_text(json.dumps({'timestamps_seconds':[0,.2,.4,.6,.8,1.],
                    'frame_sha256':[hashlib.sha256(f.tobytes()).hexdigest() for f in frames]}))
                metadata = dict(subject_id='p01',capture_group=f'g_{split}',split=split,distance=distance,lighting='indoor',
                    runtime_config_sha256=config.fingerprint(),manifest_sha256=sha256(config.manifest))
                path.with_suffix('.protocol.json').write_text(json.dumps({'collection':metadata}))
                for start,end,label,action in ((0,.39,'no_yawn','normal'),(.4,.99,'yawn','yawn'),(1,1.1,'no_yawn','smile')):
                    rows.append({**{k:metadata[k] for k in ('subject_id','capture_group','split','distance','lighting')},
                        'clip_id':path.name,'start':start,'end':end,'label':label,'action':action,'reviewed':'true'})
                for j,frame in enumerate(frames):
                    crop = frame[20:100,30:115].copy(); crops.append(crop)
            with o['annotations'].open('w',newline='') as stream:
                writer = csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
            seen = []
            def observe(frame,timestamp):
                seen.append(timestamp)
                if timestamp == .2:
                    return VisionResult('no_face')
                crop = frame[20:100,30:115].copy()
                quality = 'blurry' if timestamp == 1. else 'usable'
                return VisionResult(quality,(crop,crop,crop),(),{'sharpness':18. if quality=='blurry' else 40.})
            vision = Mock();vision.observe.side_effect = observe
            with patch('tools.finetune_yawn_distance.Vision',return_value=vision): prepare(o)
            self.assertGreaterEqual(len(seen),36)  # includes retained legacy crop work
            data = verify_prepared_dataset(o['dataset'],config,o['recipe'])
            camera_rows = [r for r in data['records'] if r['domain']=='camera']
            self.assertEqual(len(camera_rows),36)
            self.assertTrue(any(r['domain']=='static' for r in data['records']))
            self.assertFalse(any(r['domain']=='static' and r['split']=='test' for r in data['records']))
            spec = read_manifest(config.manifest)['classifiers']['yawn']
            for row,crop in zip(camera_rows,crops):
                if row['file']:
                    np.testing.assert_array_equal(cv2.imread(str(o['dataset']/row['file'])),crop)
                    self.assertEqual(row['input_sha256'],hashlib.sha256(prepare_rgb(crop,spec).tobytes()).hexdigest())
                else:
                    self.assertEqual(row['quality'],'no_face')
                    self.assertFalse(row['train_eligible'])
            self.assertTrue(all(r['train_eligible'] for r in data['records'] if r['quality']=='blurry'))
            self.assertTrue(any(r['split']=='val' and r['quality']=='blurry' for r in data['records']))
            with self.assertRaisesRegex(RuntimeError,'No candidate passed validation'):
                train(o,epochs=1)
            report = json.loads((o['output']/'validation.json').read_text())
            self.assertIsNone(report['selected'])
            self.assertEqual(report['selection_split'],'val')
            self.assertFalse(report['test_used_for_selection'])
            self.assertFalse(report['event_acceptance_measured'])
            self.assertGreater(report['baseline_validation']['camera/all']['unknown_quality'],0)
            self.assertFalse((o['output']/'best_yawn.pt').exists())
            self.assertFalse((o['output']/'manifest.json').exists())
