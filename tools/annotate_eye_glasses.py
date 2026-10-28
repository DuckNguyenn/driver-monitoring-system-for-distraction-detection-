"""Manually label glasses clips per eye; no model probability creates a label."""
from pathlib import Path
import argparse
import csv
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();video=args.video.resolve()
    output=(args.output or video.with_suffix('.eyes.csv')).resolve()
    if output.exists():raise FileExistsError('Annotation exists; use --output for a new review')
    from driver_monitor.eye_collection import recorded_times,eye_intervals
    from driver_monitor.config import load_config
    from driver_monitor.vision import Vision,orient_frame
    import cv2
    metadata,times=recorded_times(video)
    collection=metadata.get('collection',{})
    if any(not collection.get(key) for key in ('subject_id','capture_group','split')):raise ValueError('Missing recording collection metadata')
    config=load_config(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml')
    config.rotation_degrees=metadata['rotation_degrees']
    vision=Vision(config);capture=cv2.VideoCapture(str(video))
    if not capture.isOpened():raise RuntimeError('Cannot open recording')
    choices={ord('1'):('Open','Open'),ord('2'):('Closed','Closed'),ord('3'):('Closed','Open'),
             ord('4'):('Open','Closed'),ord('0'):('Unknown','Unknown'),
             ord('5'):('Unknown','Open'),ord('6'):('Open','Unknown')}
    changes=[];frame=0;paused=True;reviewed_until=0;message='Pause and choose a label at each boundary. No default labels.'
    saved=False
    try:
        while True:
            capture.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,image=capture.read()
            if not ok:raise RuntimeError('Frame decode failed')
            image=orient_frame(image,metadata['rotation_degrees']);result=vision.observe(image)
            for index,box in enumerate(result.boxes[:2] if result.boxes else ()):
                x1,y1,x2,y2=box;cv2.rectangle(image,(x1,y1),(x2,y2),(0,220,0),2)
                cv2.putText(image,str(index+1),(x1,y1-5),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,220,0),2)
            current=next((row for row in reversed(changes) if row['frame']<=frame),None)
            texts=[f'frame {frame}/{len(times)-1} | source time {times[frame]:.3f}s | '+('PAUSED' if paused else 'PLAYING'),
                   '1 Open/Open  2 Closed/Closed  3 Closed/Open  4 Open/Closed',
                   '0 Unknown/Unknown  5 Unknown/Open  6 Open/Unknown',
                   'Space play/pause | J/K step | A/D +/-10 | X undo | S save | Q exit',
                   'Eye 1 / Eye 2: '+(current['eye1']+' / '+current['eye2'] if current else 'UNLABELED'),message]
            # Keep the source face/eyes visible: controls occupy a separate panel.
            display=cv2.copyMakeBorder(image,0,146,0,0,cv2.BORDER_CONSTANT,value=(20,20,20))
            for index,text in enumerate(texts):cv2.putText(display,text,(6,image.shape[0]+20+23*index),cv2.FONT_HERSHEY_SIMPLEX,.40,(245,245,245),1,cv2.LINE_AA)
            cv2.imshow('Review eye labels',display);reviewed_until=max(reviewed_until,frame)
            wait=30 if paused or frame==len(times)-1 else max(1,min(250,round(1000*(times[frame+1]-times[frame]))))
            key=cv2.waitKey(wait)&255
            if key in (ord('q'),27):break
            if key in choices:
                if changes and frame<changes[-1]['frame']:message='Undo X before editing an earlier boundary';paused=True;continue
                label=choices[key];row={'frame':frame,'eye1':label[0],'eye2':label[1]}
                if changes and frame==changes[-1]['frame']:changes[-1]=row
                else:changes.append(row)
                message='Manual interval starts here';paused=True
            elif key==ord('x'):
                if changes:changes.pop()
                message='Last boundary removed';paused=True
            elif key==ord(' '):paused=not paused
            elif key in (ord('j'),ord('k'),ord('a'),ord('d')):
                frame=max(0,min(len(times)-1,frame+{ord('j'):-1,ord('k'):1,ord('a'):-10,ord('d'):10}[key]));paused=True
            elif key==ord('s'):
                intervals=eye_intervals(changes,times,reviewed_until)
                if not intervals:message='No manual labels to save';continue
                rows=[{'clip':video.name,**collection,**row} for row in intervals]
                output.parent.mkdir(parents=True,exist_ok=True)
                with output.open('x',encoding='utf-8',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                print('Saved reviewed eye intervals:',output,flush=True);saved=True;break
            elif not paused:
                if frame<len(times)-1:frame+=1
                else:paused=True
    finally:capture.release();cv2.destroyAllWindows()
    if not saved:print('No annotations saved; recording kept unchanged.')


if __name__=='__main__':main()
