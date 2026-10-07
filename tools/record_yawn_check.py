"""Guided camera recording for reviewing missed yawns and false smile detections.

The prompts are a recording protocol, not ground-truth annotations. Review the
saved video and fill the annotation CSV before using the clip for training.
"""
import argparse
import csv
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

PHASES = [
    (0, 5, 'NORMAL: keep mouth relaxed'),
    (5, 12, 'YAWN: one clear yawn, hold 2-3s'),
    (12, 16, 'NORMAL: relax mouth'),
    (16, 23, 'SMILE: show teeth, keep eyes visible'),
    (23, 27, 'NORMAL: relax mouth'),
    (27, 34, 'YAWN: one clear yawn, hold 2-3s'),
    (34, 38, 'NORMAL: relax mouth'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=int, default=0)
    parser.add_argument('--output-dir', default='reports/yawn_camera_check')
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    path = output / (stem+'.avi')
    cap = cv2.VideoCapture(args.source, cv2.CAP_DSHOW if platform.system()=='Windows' else cv2.CAP_ANY)
    writer = None
    timestamps = []
    complete = False
    error = None
    try:
        if not cap.isOpened():
            raise RuntimeError('Camera unavailable; close Driver monitor before recording.')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        ready = time.monotonic()
        origin = None
        print('Recording starts after a 5-second countdown in the camera window.', flush=True)
        print('Protocol: relaxed mouth, yawn, relaxed mouth, smile, relaxed mouth, yawn, relaxed mouth.', flush=True)
        while True:
            ok, frame = cap.read()
            acquired = time.monotonic()
            if not ok:
                raise RuntimeError('Camera read failed.')
            countdown = max(0., 5-(acquired-ready))
            if countdown>0:
                prompt = f'Prepare {countdown:.1f}s: full face, steady camera'
            else:
                if origin is None:
                    origin = acquired
                    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'),
                                             30., (frame.shape[1],frame.shape[0]))
                    if not writer.isOpened():
                        raise RuntimeError('Video writer unavailable.')
                elapsed = acquired-origin
                if elapsed>=PHASES[-1][1]:
                    complete = True
                    break
                writer.write(frame)  # clean source pixels; prompt is preview only
                timestamps.append(elapsed)
                prompt = next(message for a,b,message in PHASES if a<=elapsed<b)
                prompt = f'{elapsed:.1f}s | '+prompt
            preview = frame.copy()
            cv2.rectangle(preview, (0,0), (preview.shape[1],57), (20,20,20), -1)
            cv2.putText(preview, prompt, (8,24), cv2.FONT_HERSHEY_SIMPLEX, .47, (0,235,235),1,cv2.LINE_AA)
            cv2.putText(preview,'Q / Esc: finish recording', (8,47),cv2.FONT_HERSHEY_SIMPLEX,.44,(240,240,240),1,cv2.LINE_AA)
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
        cv2.destroyAllWindows()
        if timestamps:
            path.with_suffix('.timestamps.json').write_text(json.dumps({
                'source':args.source,'timestamps_seconds':timestamps,
                'note':'AVI header nominal 30 FPS; use exact capture timestamps.'}),encoding='utf-8')
            path.with_suffix('.protocol.json').write_text(json.dumps({
                'complete':complete,'fault':error,'phases':PHASES,'frames':len(timestamps),
                'duration_seconds':timestamps[-1], 'ground_truth_reviewed':False,
                'note':'Prompts are not labels. Review exact event intervals before annotation.'},indent=2),encoding='utf-8')
            with path.with_suffix('.annotations.template.csv').open('w',newline='',encoding='utf-8') as stream:
                csv.writer(stream).writerow(['subject_id','clip_id','split','lighting','start','end','label'])
            print('Saved:',path,flush=True)


if __name__=='__main__':
    main()
