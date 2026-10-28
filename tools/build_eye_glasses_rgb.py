"""Prepare only manually reviewed RGB eye crops; no model-generated labels."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection',type=Path,default=ROOT/'data_collection/eye_glasses/videos')
    parser.add_argument('--output',type=Path,default=ROOT/'data_collection/eye_glasses/rgb_supplement')
    parser.add_argument('--stride',type=int,default=2)
    args=parser.parse_args()
    if args.stride<1:parser.error('stride must be positive')
    labels=sorted(args.collection.glob('*.eyes.csv'))
    if not labels:raise ValueError('No reviewed .eyes.csv files; record and review the RGB clip first')
    destination=args.output.resolve()
    if destination.exists() and any(destination.iterdir()):raise ValueError('Output exists; keep earlier dataset unchanged')
    from driver_monitor.eye_collection import recorded_times,reviewed_eye_rows
    from driver_monitor.config import load_config
    from driver_monitor.models import sha256,read_manifest,prepare_rgb
    from driver_monitor.vision import Vision,orient_frame
    import cv2
    contexts=[];subject_owners={};group_owners={}
    for annotations in labels:
        video=annotations.with_name(annotations.name.removesuffix('.eyes.csv')+'.avi')
        metadata,times=recorded_times(video);collection=metadata['collection']
        if collection.get('glasses') is not True:raise ValueError('Expected declared clear-glasses recording')
        split=collection['split'];person=collection['subject_id'];group=collection['capture_group']
        if subject_owners.get(person,split)!=split:raise ValueError('New RGB subject crosses splits: '+person)
        if group_owners.get(group,split)!=split:raise ValueError('Capture group crosses splits: '+group)
        subject_owners[person]=split;group_owners[group]=split
        intervals=reviewed_eye_rows(annotations,metadata,times)
        if intervals:contexts.append((video,metadata,times,intervals,annotations))
    if not contexts:raise ValueError('No reviewed intervals')
    destination.mkdir(parents=True,exist_ok=True);records=[];owners={};skipped=Counter();sources=[]
    for video,metadata,times,intervals,annotations in contexts:
        settings=load_config(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml',**metadata.get('vision_settings',{}))
        spec=read_manifest(settings.manifest)['classifiers']['eye'];vision=Vision(settings)
        hashes=json.loads(video.with_suffix('.timestamps.json').read_text(encoding='utf-8'))['frame_sha256']
        cap=cv2.VideoCapture(str(video));collection=metadata['collection']
        sources.append({'video':str(video),'video_sha256':metadata['video_sha256'],'annotation_sha256':sha256(annotations),
                        'subject':collection['subject_id'],'capture_group':collection['capture_group'],'split':collection['split']})
        try:
            for interval in intervals:
                for index in range(interval['start_frame'],interval['end_frame_exclusive'],args.stride):
                    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,image=cap.read()
                    if not ok:raise RuntimeError('Frame decode failed')
                    if hashlib.sha256(image.tobytes()).hexdigest()!=hashes[index]:raise ValueError('Recorded pixels differ from source hash')
                    result=vision.observe(orient_frame(image,settings.rotation_degrees))
                    if result.crops is None:skipped['no_runtime_crop']+=2;continue
                    for eye,label in enumerate((interval['eye1'],interval['eye2'])):
                        if label=='Unknown':skipped['reviewed_unknown']+=1;continue
                        crop=result.crops[eye]
                        key=hashlib.sha256(prepare_rgb(crop,spec).tobytes()).hexdigest()
                        owner=(collection['split'],label)
                        if key in owners:
                            if owners[key]!=owner:raise ValueError('Identical eye pixels cross labels or splits')
                            skipped['duplicate_input']+=1;continue
                        owners[key]=owner
                        name=f'native/{len(records):06d}.png';path=destination/name;path.parent.mkdir(exist_ok=True)
                        if not cv2.imwrite(str(path),crop):raise OSError('Crop write failed')
                        records.append({'file':name,'sha256':sha256(path),'input_sha256':key,'label':label,'split':collection['split'],
                                        'domain':'rgb_rehearsal','source':video.stem,'subject':collection['subject_id'],
                                        'capture_group':collection['capture_group'],'glasses':True,'glasses_type':collection['glasses_type'],
                                        'frame':index,'eye_index':eye,'timestamp':times[index],'source_frame_sha256':hashes[index],
                                        'runtime_image_quality':result.quality,'runtime_eye_quality':result.eye_quality,
                                        'quality':result.quality,'new_glasses_camera':True,'resolution':'RGB_camera_native','reviewed':True})
        finally:cap.release()
    if not records:raise ValueError('No reviewed, readable labeled eye crops')
    counts=Counter((r['split'],r['label']) for r in records)
    summary={'kind':'driver_monitor_eye_rgb_supplement','records':records,'sources':sources,'runtime_spec':spec,
             'subject_split_verified':True,'new_rgb_glasses_camera_present':True,'automatic_eye_labels':False,
             'image_quality_gate_acceptance':False,'live_camera_accuracy_measured':False,
             'validation_test_present':all(counts[s,l]>0 for s in ('val','test') for l in ('Closed','Open')),
             'counts':{str(k):v for k,v in counts.items()},'skipped':dict(skipped)}
    (destination/'dataset.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('records','sources','runtime_spec')},indent=2))


if __name__=='__main__':main()
