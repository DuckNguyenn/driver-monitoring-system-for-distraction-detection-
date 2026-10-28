"""Reviewed eye intervals use recorded source timestamps, never prompts or AVI FPS."""
from math import isfinite
from pathlib import Path
import json
import csv

LABELS={'Open','Closed','Unknown'}


def recorded_times(video,verify=True):
    from .models import sha256
    video=Path(video)
    metadata=json.loads(video.with_suffix('.metadata.json').read_text(encoding='utf-8'))
    timing=json.loads(video.with_suffix('.timestamps.json').read_text(encoding='utf-8'))
    times=timing['timestamps_seconds']
    if not times or len(times)!=metadata['frames'] or any(not isfinite(t) or t<0 for t in times):
        raise ValueError('Invalid recorded timestamps')
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Non-increasing recorded timestamps')
    if verify and sha256(video)!=metadata['video_sha256']:raise ValueError('Recorded video checksum changed')
    return metadata,times


def eye_intervals(changes,times,last_reviewed_frame):
    if not 0<=last_reviewed_frame<len(times):raise ValueError('Invalid last reviewed frame')
    previous=-1;result=[]
    for index,change in enumerate(changes):
        frame=change['frame']
        if not isinstance(frame,int) or frame<=previous or not 0<=frame<=last_reviewed_frame:raise ValueError('Annotation frame order invalid')
        if change['eye1'] not in LABELS or change['eye2'] not in LABELS:raise ValueError('Invalid eye label')
        end=changes[index+1]['frame'] if index+1<len(changes) else last_reviewed_frame+1
        if end>last_reviewed_frame+1 or end<=frame:raise ValueError('Invalid interval end')
        result.append({'start_frame':frame,'end_frame_exclusive':end,'start':times[frame],
                       'end':times[end] if end<len(times) else times[-1]+1e-6,
                       'eye1':change['eye1'],'eye2':change['eye2'],'reviewed':True})
        previous=frame
    return result


def reviewed_eye_rows(path,metadata,times):
    collection=metadata['collection'];result=[];previous_end=0
    with Path(path).open(encoding='utf-8',newline='') as stream:
        for row in csv.DictReader(stream):
            if row.get('reviewed','').casefold()!='true':continue
            for key in ('subject_id','capture_group','split'):
                if row[key]!=str(collection[key]):raise ValueError('Annotation collection metadata changed: '+key)
            start,end=int(row['start_frame']),int(row['end_frame_exclusive'])
            if not previous_end<=start<end<=len(times):raise ValueError('Overlapping or invalid frame intervals')
            if row['eye1'] not in LABELS or row['eye2'] not in LABELS:raise ValueError('Invalid eye class')
            expected_end=times[end] if end<len(times) else times[-1]+1e-6
            if abs(float(row['start'])-times[start])>1e-5 or abs(float(row['end'])-expected_end)>1e-5:
                raise ValueError('Annotation source timestamps changed')
            result.append({**row,'start_frame':start,'end_frame_exclusive':end})
            previous_end=end
    return result
