import json
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from driver_monitor.config import Config, ROOT
from driver_monitor.models import read_manifest
from driver_monitor.vision import VisionResult
from tools.record_yawn_check import YawnInputInspector, FaceSizeGuide
from tools import record_yawn_check


class YawnRecordingDiagnosticsTests(unittest.TestCase):
    def test_face_size_guide_reports_small_faces_without_mutating_camera_or_runtime(self):
        config = Config(min_face_size=80,face_margin=.10)
        guide = FaceSizeGuide.__new__(FaceSizeGuide)
        guide.config, guide.target, guide.vision = config,100,Mock()
        frame = np.full((480,640,3),70,np.uint8); before = frame.copy()
        small = np.full((110,87,3),100,np.uint8)
        guide.vision.observe.return_value = VisionResult('usable',(small,small,small))
        enough,caption = guide.inspect(frame,1.)
        self.assertFalse(enough);self.assertIn('MOVE CLOSER',caption)
        large = np.full((120,104,3),100,np.uint8)
        guide.vision.observe.return_value = VisionResult('blurry',(large,large,large))
        enough,caption = guide.inspect(frame,2.)
        self.assertTrue(enough);self.assertIn('blurry',caption)
        np.testing.assert_array_equal(frame,before)
        self.assertEqual(config.min_face_size,80)

    def inspector(self, quality):
        inspector = YawnInputInspector.__new__(YawnInputInspector)
        inspector.config = Config()
        self.crop = np.full((120, 70, 3), [10, 30, 100], np.uint8)
        inspector.vision = Mock()
        inspector.vision.observe.return_value = VisionResult(quality, (self.crop,self.crop,self.crop), (), {})
        spec = read_manifest(ROOT/'models/yawn_camera_refined/manifest.json')['classifiers']['yawn']
        inspector.classifier = Mock(spec=types.SimpleNamespace())
        inspector.classifier.spec = spec
        inspector.classifier.predict = Mock(return_value={'yawn':.2,'no_yawn':.8})
        inspector.classifier.last_views = {'center':{'yawn':.2,'no_yawn':.8}}
        return inspector

    def test_inspection_does_not_paint_over_camera_or_model_inputs(self):
        inspector = self.inspector('usable')
        raw = np.full((480,640,3),70,np.uint8);before=raw.copy();crop_before=self.crop.copy()
        panel,detail = inspector.inspect(raw,3.)
        np.testing.assert_array_equal(raw,before)
        np.testing.assert_array_equal(self.crop,crop_before)
        self.assertEqual(detail['score'],.2)
        self.assertEqual(detail['quality'],'usable')
        self.assertGreaterEqual(panel.shape[0],224)

    def test_unusable_pixels_do_not_receive_a_yawn_score(self):
        inspector=self.inspector('blurry')
        panel,detail=inspector.inspect(np.zeros((480,640,3),np.uint8),2.)
        inspector.classifier.predict.assert_not_called()
        self.assertIsNone(detail['score'])
        self.assertEqual(detail['quality'],'blurry')

    def test_recording_saves_clean_frames_and_aligned_probe_timestamps(self):
        generator = np.random.default_rng(42)
        frames = [generator.integers(0,256,(480,640,3),dtype=np.uint8),
                  np.full((480,640,3),[15,80,160],np.uint8),
                  np.full((480,640,3),120,np.uint8)]
        camera = Mock()
        camera.isOpened.return_value = True
        camera.read.side_effect = [(True,frame) for frame in frames]
        inspector = Mock()
        inspector.inspect.return_value = (np.zeros((284,224,3),np.uint8),
            {'quality':'no_face','score':None,'views':{},'boxes':[],'metrics':{}})
        inspector.classifier.spec = {'inference_views':['center']}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = output/'manifest.json'
            manifest.write_text('{}',encoding='utf-8')
            inspector.config.manifest = manifest
            inspector.config.fingerprint.return_value = 'test-config'
            args = ['record_yawn_check.py','--source','0','--inspect-model','--output-dir',str(output)]
            with patch('sys.argv',args), patch.object(record_yawn_check.cv2,'VideoCapture',return_value=camera), \
                    patch.object(record_yawn_check,'YawnInputInspector',return_value=inspector), \
                    patch.object(record_yawn_check.time,'monotonic',side_effect=[0.,5.1,5.2,5.3]), \
                    patch.object(record_yawn_check.cv2,'imshow'), \
                    patch.object(record_yawn_check.cv2,'waitKey',side_effect=[-1,-1,ord('q')]), \
                    patch.object(record_yawn_check.cv2,'destroyAllWindows'):
                record_yawn_check.main()
            video, = output.glob('*.avi')
            timestamps = json.loads(video.with_suffix('.timestamps.json').read_text(encoding='utf-8'))['timestamps_seconds']
            probes = [json.loads(line) for line in video.with_suffix('.probe.jsonl').read_text(encoding='utf-8').splitlines()]
            np.testing.assert_allclose(timestamps,[0.,.1,.2])
            self.assertEqual([p['timestamp'] for p in probes],timestamps)
            self.assertEqual([p['frame'] for p in probes],[0,1,2])
            self.assertTrue(all(p['score'] is None for p in probes))
            protocol = json.loads(video.with_suffix('.protocol.json').read_text(encoding='utf-8'))
            self.assertFalse(protocol['ground_truth_reviewed'])
            self.assertFalse(protocol['complete'])
            self.assertEqual(protocol['frames'],3)
            decoded = cv2.VideoCapture(str(video))
            try:
                for original in frames:
                    ok,frame = decoded.read()
                    self.assertTrue(ok)
                    # Even tiny compression changes can alter the yawn score.
                    np.testing.assert_array_equal(frame,original)
                self.assertFalse(decoded.read()[0])
            finally:
                decoded.release()
            self.assertEqual(protocol['video_codec'],'FFV1')
            metadata=json.loads(video.with_suffix('.timestamps.json').read_text(encoding='utf-8'))
            self.assertEqual(metadata['frame_sha256'],[hashlib.sha256(f.tobytes()).hexdigest() for f in frames])
        camera.release.assert_called_once()
        inspector.close.assert_called_once()
