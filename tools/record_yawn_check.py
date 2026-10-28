"""Guided camera recording for reviewing missed yawns and false smile detections.

The prompts are a recording protocol, not ground-truth annotations. Review the
saved video and fill the annotation CSV before using the clip for training.
"""
import argparse
import csv
import hashlib
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FaceSizeGuide:
    """CPU-only collection guide; small faces are measured, never AI-scored.

    The saved runtime fingerprint keeps its original face-size gate. This
    preview uses a relaxed size filter solely to display undersized faces.
    """
    def __init__(self, config):
        from dataclasses import replace
        from driver_monitor.vision import Vision
        self.config = config
        self.vision = Vision(replace(config, min_face_size=1))
        self.target = math.ceil(config.min_face_size * (1 + 2 * config.face_margin)) + 4

    def inspect(self, frame, timestamp):
        from driver_monitor.vision import orient_frame
        result = self.vision.observe(orient_frame(frame, self.config.rotation_degrees), timestamp)
        if result.crops is None:
            return False, f'Face: {result.quality}; show full face to camera'
        short_side = min(result.crops[2].shape[:2])
        enough = short_side >= self.target
        caption = f'Face crop min:{short_side}px | target:{self.target}px | {result.quality}'
        caption += ' | SIZE OK' if enough else ' | MOVE CLOSER'
        return enough, caption


class YawnInputInspector:
    """Show the actual classifier inputs while saving the camera without overlays."""
    def __init__(self, config):
        from driver_monitor.config import load_config
        from driver_monitor.models import Classifier
        from driver_monitor.vision import Vision
        self.config = load_config(config)
        self.vision = Vision(self.config)
        self.classifier = Classifier(self.config.manifest, 'yawn', self.config.backend, self.config.cpu_threads)

    def inspect(self, frame, timestamp):
        from driver_monitor.models import edge_pad_square, prepare_rgb
        from driver_monitor.vision import orient_frame
        result = self.vision.observe(orient_frame(frame, self.config.rotation_degrees), timestamp)
        names = self.classifier.spec.get('inference_views', ['center'])
        panel = np.full((284, 224*len(names), 3), 24, np.uint8)
        score = None
        values = {}
        input_hashes = {}
        if result.crops is not None:
            crop = result.crops[2]
            if result.quality == 'usable':
                prediction = self.classifier.predict(crop)
                score = next(v for k,v in prediction.items() if k.casefold() == 'yawn')
                values = self.classifier.last_views
            for i,name in enumerate(names):
                view = crop if name == 'center' else edge_pad_square(crop)
                rgb = prepare_rgb(view,self.classifier.spec)
                input_hashes[name] = hashlib.sha256(rgb.tobytes()).hexdigest()
                panel[26:250,224*i:224*(i+1)] = rgb[:,:,::-1]
                probability = next((v for k,v in values.get(name,{}).items() if k.casefold() == 'yawn'),None)
                title = f'{name}: '+('?' if probability is None else f'{probability:.3f}')
                cv2.putText(panel,title,(224*i+5,17),cv2.FONT_HERSHEY_SIMPLEX,.38,(230,230,230),1,cv2.LINE_AA)
        caption = f"{result.quality} | score:"+('?' if score is None else f'{score:.3f}')
        cv2.putText(panel,caption,(5,271),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,220,220),1,cv2.LINE_AA)
        return panel, {'quality':result.quality,'score':score,'views':values,'boxes':result.boxes,
                       'metrics':result.metrics,'input_sha256':input_hashes}

    def close(self):
        self.classifier.close()

PHASES = [
    (0, 5, 'NORMAL: keep mouth relaxed'),
    (5, 12, 'YAWN: one clear yawn, hold 2-3s'),
    (12, 16, 'NORMAL: relax mouth'),
    (16, 23, 'SMILE: show teeth, keep eyes visible'),
    (23, 27, 'NORMAL: relax mouth'),
    (27, 34, 'YAWN: one clear yawn, hold 2-3s'),
    (34, 38, 'NORMAL: relax mouth'),
]
DISTANCE_PHASES = PHASES + [
    (38, 44, 'TALK: speak normally, keep head steady'),
    (44, 48, 'NORMAL: relax mouth'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=int, default=0)
    parser.add_argument('--output-dir', default='reports/yawn_camera_check')
    parser.add_argument('--config', default=str(ROOT/'configs/camera_pc.yaml'))
    parser.add_argument('--inspect-model', action='store_true', help='Show the exact 224x224 inputs and record per-view scores; raw video has no overlays')
    parser.add_argument('--distance', choices=('near','medium','far'), help='Enable the 48-second distance collection protocol; keep this distance for the whole clip')
    parser.add_argument('--subject-id')
    parser.add_argument('--capture-group', help='All clips from the same sitting must share this ID and split')
    parser.add_argument('--split', choices=('train','val','test'))
    parser.add_argument('--lighting', default='indoor')
    parser.add_argument('--guide-face-size', action='store_true', help='CPU-only crop-size guide; wait for sufficient face size before the countdown')
    args = parser.parse_args()
    if args.distance and not all((args.subject_id,args.capture_group,args.split)):
        parser.error('--distance requires --subject-id, --capture-group and --split')
    phases = DISTANCE_PHASES if args.distance else PHASES
    distance_config = None
    if args.distance or args.guide_face_size:
        from driver_monitor.config import load_config
        distance_config = load_config(args.config)
    guide = FaceSizeGuide(distance_config) if args.guide_face_size else None
    guide_ready, guide_text, last_guide = not args.guide_face_size, '', -float('inf')
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    path = output / (stem+'.avi')
    cap = cv2.VideoCapture(args.source, cv2.CAP_DSHOW if platform.system()=='Windows' else cv2.CAP_ANY)
    writer = None
    timestamps = []
    frame_hashes = []
    complete = False
    error = None
    inspector = probe_stream = None
    try:
        if not cap.isOpened():
            raise RuntimeError('Camera unavailable; close Driver monitor before recording.')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, distance_config.width if distance_config else 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, distance_config.height if distance_config else 480)
        if args.inspect_model:
            inspector = YawnInputInspector(args.config)
        ready = time.monotonic()
        origin = None
        print('Recording starts after a 5-second countdown in the camera window.', flush=True)
        print('Protocol: relaxed mouth, yawn, relaxed mouth, smile, relaxed mouth, yawn, relaxed mouth.', flush=True)
        if args.distance:
            print(f'Distance: {args.distance}; do not change distance within this clip. Talk normally during the final prompt.',flush=True)
        while True:
            ok, frame = cap.read()
            acquired = time.monotonic()
            if not ok:
                raise RuntimeError('Camera read failed.')
            if guide is not None and acquired - last_guide >= .2:
                guide_ready, guide_text = guide.inspect(frame, acquired)
                last_guide = acquired
            if origin is None and not guide_ready:
                ready = acquired  # do not consume the countdown on an undersized face
            countdown = max(0., 5-(acquired-ready))
            if countdown>0:
                prompt = ('WAIT: move closer; keep full face visible' if not guide_ready else
                          f'Prepare {countdown:.1f}s: full face, steady camera')
            else:
                if origin is None:
                    origin = acquired
                    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'FFV1'),
                                             30., (frame.shape[1],frame.shape[0]))
                    if not writer.isOpened():
                        raise RuntimeError('Lossless FFV1 writer unavailable; install OpenCV with FFmpeg support.')
                    if inspector:
                        probe_stream = path.with_suffix('.probe.jsonl').open('x',encoding='utf-8')
                elapsed = acquired-origin
                if elapsed>=phases[-1][1]:
                    complete = True
                    break
                writer.write(frame)  # clean source pixels; prompt is preview only
                timestamps.append(elapsed)
                frame_hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
                prompt = next(message for a,b,message in phases if a<=elapsed<b)
                prompt = f'{elapsed:.1f}s | '+prompt
                if args.distance:
                    prompt = args.distance.upper()+' | '+prompt
            if inspector:
                panel, detail = inspector.inspect(frame, acquired)
                cv2.imshow('Yawn model input (224x224)',panel)
                if probe_stream is not None:
                    probe_stream.write(json.dumps({'timestamp':elapsed,'frame':len(timestamps)-1,**detail},allow_nan=False)+'\n')
                    probe_stream.flush()
            preview = frame.copy()
            cv2.rectangle(preview, (0,0), (preview.shape[1],80 if guide else 57), (20,20,20), -1)
            cv2.putText(preview, prompt, (8,24), cv2.FONT_HERSHEY_SIMPLEX, .47, (0,235,235),1,cv2.LINE_AA)
            cv2.putText(preview,'Q / Esc: finish recording', (8,47),cv2.FONT_HERSHEY_SIMPLEX,.44,(240,240,240),1,cv2.LINE_AA)
            if guide:
                cv2.putText(preview,guide_text,(8,70),cv2.FONT_HERSHEY_SIMPLEX,.43,
                            (80,230,80) if guide_ready else (0,200,255),1,cv2.LINE_AA)
            cv2.imshow('Yawn recording check', preview)
            if cv2.waitKey(1)&255 in (ord('q'),27):
                break
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        if probe_stream is not None:
            probe_stream.close()
        if inspector is not None:
            inspector.close()
        cv2.destroyAllWindows()
        if timestamps:
            from driver_monitor.models import sha256
            path.with_suffix('.timestamps.json').write_text(json.dumps({
                'source':args.source,'timestamps_seconds':timestamps,'frame_sha256':frame_hashes,
                'frame_hash_format':'decoded BGR uint8 HWC contiguous bytes',
                'note':'Lossless FFV1 AVI; header nominal 30 FPS; use exact capture timestamps.'}),encoding='utf-8')
            diagnostics = None
            if inspector:
                from driver_monitor.models import sha256
                diagnostics = {'config':str(Path(args.config).resolve()),'manifest_sha256':sha256(inspector.config.manifest),
                    'config_sha256':inspector.config.fingerprint(),'inference_views':inspector.classifier.spec.get('inference_views',['center']),
                    'note':'Per-view scores are diagnostics, not event labels or accuracy; inspect-model does not control the buzzer.'}
            path.with_suffix('.protocol.json').write_text(json.dumps({
                'complete':complete,'fault':error,'phases':phases,'frames':len(timestamps),
                'collection':{'subject_id':args.subject_id,'capture_group':args.capture_group,
                    'split':args.split,'distance':args.distance,'lighting':args.lighting,
                    'config':str(Path(args.config).resolve()),
                    'runtime_config_sha256':distance_config.fingerprint() if distance_config else None,
                    'manifest_sha256':sha256(distance_config.manifest) if distance_config else None},
                'video_codec':'FFV1','pixel_fidelity':'lossless; verify decoded BGR bytes against frame_sha256',
                'face_size_guide':{'enabled':bool(guide),'target_native_crop_short_side':guide.target if guide else None,
                    'note':'Preview guide only; runtime size/quality gates are unchanged.'},
                'duration_seconds':timestamps[-1], 'ground_truth_reviewed':False,
                'diagnostics':diagnostics,
                'note':'Prompts are not labels. Review exact event intervals before annotation.'},indent=2),encoding='utf-8')
            with path.with_suffix('.annotations.template.csv').open('w',newline='',encoding='utf-8') as stream:
                csv.writer(stream).writerow(['subject_id','clip_id','split','lighting','start','end','label'])
            print('Saved:',path,flush=True)


if __name__=='__main__':
    main()
