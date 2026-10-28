"""Manually review clean FFV1 clips using exact sidecar time, not AVI header FPS.

Start/end an interval with S/E; 1 normal, 2 yawn, 3 smile, 4 talking.
Space pauses, A/D jumps by two seconds. Only explicitly marked intervals save.
"""
import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from driver_monitor.yawn_distance import FIELDS

LABELS = {ord('1'):('no_yawn','normal'), ord('2'):('yawn','yawn'),
          ord('3'):('no_yawn','smile'), ord('4'):('no_yawn','talk')}


def append_reviewed(path, intervals):
    path = Path(path)
    existing = []
    if path.is_file():
        with path.open(encoding='utf-8-sig',newline='') as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != FIELDS:
                raise ValueError('annotation CSV header differs')
            existing = list(reader)
    if any(r['clip_id'] == intervals[0]['clip_id'] for r in existing):
        raise ValueError('clip already annotated; review/edit its existing CSV rows instead')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=FIELDS); writer.writeheader()
        writer.writerows(existing + intervals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--annotations',type=Path,default=ROOT/'data_collection/yawn_distance/annotations.csv')
    parser.add_argument('--videos',type=Path,default=ROOT/'data_collection/yawn_distance/videos')
    args = parser.parse_args()
    path = args.video.resolve(); videos = args.videos.resolve()
    if not path.is_relative_to(videos): parser.error('video must be inside --videos directory')
    protocol = json.loads(path.with_suffix('.protocol.json').read_text(encoding='utf-8'))
    metadata = protocol.get('collection') or {}
    if not all(metadata.get(k) for k in ('subject_id','capture_group','split','distance','lighting')):
        parser.error('record this clip with --distance, --subject-id, --capture-group and --split')
    sidecar = json.loads(path.with_suffix('.timestamps.json').read_text(encoding='utf-8'))
    timestamps = np.asarray(sidecar['timestamps_seconds'],dtype=float)
    hashes = sidecar['frame_sha256']
    if len(hashes) != len(timestamps) or not np.isfinite(timestamps).all() or any(np.diff(timestamps) <= 0):
        parser.error('invalid sidecar timestamps/hashes')
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened(): parser.error('video cannot open')
    i = 0; paused = True; label, action = LABELS[ord('1')]
    start = None; intervals = []; frame = None; deadline = time.monotonic()
    print('Space: play/pause; A/D: -/+2s; J/K: -/+1 frame; 1 normal, 2 yawn, 3 smile, 4 talk; S start, E end; Q save reviewed intervals.')
    try:
        while True:
            if frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES,i)
                ok, frame = cap.read()
                if not ok: raise ValueError('decoded frame missing')
                if hashlib.sha256(frame.tobytes()).hexdigest() != hashes[i]:
                    raise ValueError('frame pixels differ from recording')
            preview = frame.copy()
            cv2.rectangle(preview,(0,0),(preview.shape[1],78),(20,20,20),-1)
            text = f't:{timestamps[i]:.3f}s | {action} | '+('PAUSED' if paused else 'PLAY')
            cv2.putText(preview,text,(8,22),cv2.FONT_HERSHEY_SIMPLEX,.47,(0,235,235),1)
            cv2.putText(preview,'1 normal 2 yawn 3 smile 4 talk | S start E end',(8,45),cv2.FONT_HERSHEY_SIMPLEX,.43,(235,235,235),1)
            cv2.putText(preview,f'Start: {start} | saved intervals: {len(intervals)} | Q save',(8,67),cv2.FONT_HERSHEY_SIMPLEX,.43,(235,235,235),1)
            cv2.imshow('Review yawn distance clip',preview)
            key = cv2.waitKey(10) & 255
            if key in (ord('q'),27): break
            if key == ord(' '): paused = not paused; deadline = time.monotonic()
            if key in LABELS:
                if start is not None: print('End the current interval with E before changing label.')
                else: label,action = LABELS[key]
            if key == ord('s') and start is None: start = float(timestamps[i])
            if key == ord('e') and start is not None:
                end = float(timestamps[i])
                if end > start and not any(start < r['end'] and end > r['start'] for r in intervals):
                    intervals.append({**{k:metadata[k] for k in ('subject_id','capture_group','split','distance','lighting')},
                        'clip_id':path.relative_to(videos).as_posix(), 'start':start,'end':end,
                        'label':label,'action':action,'reviewed':'true'})
                    print(f'Marked {action}: {start:.3f}-{end:.3f}s'); start = None
                else: print('Interval empty or overlapping; adjust its endpoints.')
            if key in (ord('a'),ord('d')):
                target = timestamps[i] + (-2 if key == ord('a') else 2)
                i = min(len(timestamps)-1,max(0,int(np.searchsorted(timestamps,target))))
                frame = None; deadline = time.monotonic()
            elif key in (ord('j'),ord('k')):
                i = min(len(timestamps)-1,max(0,i+(-1 if key == ord('j') else 1)))
                paused = True; frame = None
            elif not paused and time.monotonic() >= deadline:
                if i < len(timestamps)-1:
                    deadline = time.monotonic()+float(timestamps[i+1]-timestamps[i]); i += 1; frame = None
                else: paused = True
    finally:
        cap.release(); cv2.destroyAllWindows()
    if start is not None: print('Unfinished interval omitted; close it with E on the next review.')
    if intervals:
        append_reviewed(args.annotations,intervals); print(f'Saved reviewed intervals: {args.annotations}')
    else: print('No labeled intervals saved; prompts were not converted to labels.')


if __name__ == '__main__':
    main()
