"""Replay yawn probabilities from a camera log without opening the camera."""
import argparse
import csv
import json
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from driver_monitor.core import Monitor, MonitorConfig, Observation


def distribution(value, positive, negative):
    return None if value == '' else {positive: float(value), negative: 1-float(value)}


def replay(rows, config, start, end, suppress_quality=False, suppress_motion=False):
    monitor = Monitor(config)
    origin = float(rows[0]['timestamp'])
    longest = interval_longest = 0.
    events = 0
    previous_count = 0
    for row in rows:
        timestamp = float(row['timestamp'])
        observation = Observation(timestamp,
            distribution(row['left_closed'], 'Closed', 'Open'),
            distribution(row['right_closed'], 'Closed', 'Open'),
            distribution(row['yawn_raw_probability'], 'yawn', 'no_yawn'),
            quality='usable' if suppress_quality else row['quality'],
            eye_quality='usable' if suppress_motion else row['eye_quality'])
        status = monitor.update(observation)
        longest = max(longest, status.yawn_candidate_seconds)
        if start <= timestamp-origin <= end:
            interval_longest = max(interval_longest, status.yawn_candidate_seconds)
            events += status.yawn_state == 'yawn' and previous_count != status.yawn_count
        previous_count = status.yawn_count
    return {'max_candidate_seconds':longest, 'interval_max_candidate_seconds':interval_longest,
            'interval_confirmed_yawns':events, 'final_60s_yawn_count':status.yawn_count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True)
    parser.add_argument('--start', type=float, default=112)
    parser.add_argument('--end', type=float, default=116)
    parser.add_argument('--expect-yawn', action='store_true')
    parser.add_argument('--output', default='reports/yawn_trace_diagnosis.json')
    args = parser.parse_args()
    if args.end<=args.start or args.start<0:
        parser.error('Require 0 <= start < end.')
    source = Path(args.csv).resolve()
    with source.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        parser.error('Trace is empty.')
    with source.with_suffix('.jsonl').open(encoding='utf-8') as stream:
        startup = json.loads(next(stream))
    parameters = startup['config']['monitor']
    variants = {
        'current': replay(rows,MonitorConfig(**parameters),args.start,args.end),
        'without_ema': replay(rows,MonitorConfig(**(parameters|{'yawn_smoothing_seconds':0})),args.start,args.end),
        'suppress_frame_quality': replay(rows,MonitorConfig(**parameters),args.start,args.end,suppress_quality=True),
        'suppress_eye_motion': replay(rows,MonitorConfig(**parameters),args.start,args.end,suppress_motion=True),
    }
    origin = float(rows[0]['timestamp'])
    interval = [r for r in rows if args.start<=float(r['timestamp'])-origin<=args.end]
    if not interval:
        parser.error('Interval has no frames.')
    raw = [float(r['yawn_raw_probability']) for r in interval if r['yawn_raw_probability']]
    result = {'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'interval_seconds':[args.start,args.end],'interval_frames':len(interval),
        'interval_usable_frames':sum(r['quality']=='usable' for r in interval),
        'raw_range':None if not raw else [min(raw),max(raw)], 'variants':variants,
        'limitations':'Probability replay only; image pixels, track changes and live frame ages are not in CSV. No independently annotated video.'}
    destination = Path(args.output).resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    if args.expect_yawn and not variants['current']['interval_confirmed_yawns']:
        raise SystemExit('FAIL: reported yawn interval has no confirmed event.')


if __name__=='__main__':
    main()
