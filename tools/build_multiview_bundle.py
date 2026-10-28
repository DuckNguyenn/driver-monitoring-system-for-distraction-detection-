"""Build a private GPU bundle from per-eye, visually reviewed multiview frames."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter,defaultdict
import csv
import copy
import hashlib
import json
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import cv2
import numpy as np
from driver_monitor.config import load_config
from driver_monitor.models import prepare_rgb,read_manifest,artifact_path,sha256
from driver_monitor.vision import Vision

CLIPS=['WIN_20261013_17_05_46_Pro','WIN_20261013_17_07_01_Pro','WIN_20261013_17_07_34_Pro']
SPLITS={CLIPS[0]:'train',CLIPS[1]:'test',CLIPS[2]:'train'}


def reviewed_labels(clip,index):
    # Manual source/face/eye-crop inspection of all 17 contact sheets.
    # No label below is inferred from a model probability or a smile/yawn eye state.
    left,right='Open','Open'
    if clip==CLIPS[0]:
        if index in (60,330):left='Closed'
        if index in (70,200,210,460):left='Unknown'
        if index in (20,30,100,150,160,200,210,330,460):right='Closed'
        yawn='yawn' if index in range(230,281,10) or index in range(310,351,10) else 'no_yawn'
        action='yawn' if yawn=='yawn' else 'smile' if index in (380,390,400,410,430,440,450,460,470) else 'normal_or_eye_action'
    elif clip==CLIPS[1]:
        if index in (30,40,230,240,260,270,370,410):left='Closed'
        if index in (70,):left='Unknown'
        if index in (70,80,230,240,260,270,370,390):right='Closed'
        if index in (90,400):right='Unknown'
        yawn='yawn' if index in (120,130,140,150,180,190,200,210) else 'Unknown' if index==110 else 'no_yawn'
        action='yawn' if yawn=='yawn' else 'smile' if index in (290,300,310,340,350) else 'normal_or_eye_action'
    else:
        if index in (40,230):left='Closed'
        if index in (100,110,130,170,190):left='Unknown'
        if index in (60,210):right='Closed'
        if index in (100,130,170,190,220):right='Unknown'
        yawn='yawn' if index in (80,90,100,110,130,140,150,240,250,260) else 'no_yawn'
        action='yawn' if yawn=='yawn' else 'smile' if index in (170,180) else 'normal_or_eye_action'
    return [left,right],yawn,action


def letterbox(frame):
    height,width=frame.shape[:2];scale=min(640/width,480/height)
    resized=cv2.resize(frame,(round(width*scale),round(height*scale)),interpolation=cv2.INTER_AREA)
    oy=(480-resized.shape[0])//2;ox=(640-resized.shape[1])//2
    result=np.zeros((480,640,3),np.uint8)
    result[oy:oy+resized.shape[0],ox:ox+resized.shape[1]]=resized
    return result


def build():
    destination=ROOT/'kaggle_upload/multiview_20261013'
    if destination.exists() and any(destination.iterdir()):raise ValueError('Bundle folder already contains data')
    destination.mkdir(parents=True,exist_ok=True)
    config=load_config(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml')
    base=read_manifest(config.manifest)
    records=[];annotations=[];sources=[];raw_owners={};prepared_owners={};label_owners={}
    def add(crop,meta,name):
        spec=base['classifiers'][name];rgb=prepare_rgb(crop,spec)
        input_digest=hashlib.sha256(rgb.tobytes()).hexdigest()
        owner=(meta['split'],meta['label'])
        key=(name,input_digest)
        if key in prepared_owners and prepared_owners[key][0]!=owner[0]:
            raise ValueError('Prepared pixels cross split boundaries')
        if key in label_owners and label_owners[key]!=owner[1]:raise ValueError('Identical pixels have conflicting labels')
        prepared_owners[key]=owner;label_owners[key]=owner[1]
        path=destination/'native'/name/f'{len(records):06d}.png';path.parent.mkdir(exist_ok=True,parents=True)
        if not cv2.imwrite(str(path),crop):raise OSError('Cannot write native crop')
        records.append({**meta,'task':name,'file':path.relative_to(destination).as_posix(),
                        'sha256':sha256(path),'input_sha256':input_digest,'native_shape':list(crop.shape),
                        'train_eligible':meta['split']=='train'})

    # Preserve existing validation/test ownership before retaining any old training crop.
    eye_data=json.loads((ROOT/'.cache/eye_refinement_v4/records.json').read_text(encoding='utf-8'))['records']
    for row in eye_data:
        if row['variant']=='base':
            for key in (row['sha256'],row['input_sha256']):raw_owners[key]=max(raw_owners.get(key,0),{'train':0,'val':1,'test':2}[row['split']])
    counts=Counter();previous_path=None;image=None;result=None
    for row in eye_data:
        if row['variant']!='base' or row['split'] not in ('train','val'):continue
        if max(raw_owners[row['sha256']],raw_owners[row['input_sha256']])>{'train':0,'val':1}[row['split']]:continue
        source=row['source'];key=(row['split'],source,row['label'])
        limit=240 if row['split']=='train' and source=='legacy' else 160 if row['split']=='train' else 1000
        if counts[key]>=limit:continue
        path=ROOT/row['path']
        if sha256(path)!=row['sha256']:raise ValueError('Retained eye image changed')
        if row['path']!=previous_path:
            previous_path=row['path'];image=cv2.imread(str(path));result=Vision(config).observe(image) if source=='roi' else None
        crop=image if source=='legacy' else None if result.crops is None else result.crops[row['eye_index']]
        if crop is None:continue
        digest=hashlib.sha256(prepare_rgb(crop,base['classifiers']['eye']).tobytes()).hexdigest()
        if digest!=row['input_sha256']:raise ValueError('Retained eye preprocessing changed')
        add(crop,{'label':row['label'],'split':row['split'],'domain':'static','source':source,
                  'parent_id':row['sha256'],'quality':'usable','resolution':'original','angle':'unspecified'},'eye')
        counts[key]+=1
    old_folder=ROOT/'.cache/yawn_near_medium/dataset'
    yawn_data=json.loads((old_folder/'dataset.json').read_text(encoding='utf-8'))['records']
    for row in yawn_data:
        path=old_folder/row['file']
        if sha256(path)!=row['sha256']:raise ValueError('Retained yawn crop changed')
        crop=cv2.imread(str(path))
        if hashlib.sha256(prepare_rgb(crop,base['classifiers']['yawn']).tobytes()).hexdigest()!=row['input_sha256']:raise ValueError('Retained yawn preprocessing changed')
        add(crop,{'label':row['label'],'split':row['split'],'domain':row['domain'],'source':row['source'],
                  'parent_id':row['sha256'],'quality':row.get('quality','usable'),
                  'resolution':'original','angle':'previous_near_medium'},'yawn')

    for clip in CLIPS:
        path=Path(r'C:\Users\P1 Gen 5\Pictures\Camera Roll')/(clip+'.mp4')
        sources.append({'file':str(path),'sha256':sha256(path),'split':SPLITS[clip]})
        cap=cv2.VideoCapture(str(path));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
        detectors={resolution:Vision(config) for resolution in ('native_1080','letterbox_640')}
        for index in range(0,count,10):
            cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read()
            if not ok:raise RuntimeError('Cannot decode annotated frame')
            timestamp=cap.get(cv2.CAP_PROP_POS_MSEC)/1000.
            eye_labels,yawn_label,action=reviewed_labels(clip,index)
            annotations.append({'clip':clip,'frame':index,'timestamp':timestamp,'split':SPLITS[clip],
                                'left_eye':eye_labels[0],'right_eye':eye_labels[1],'yawn':yawn_label,'action':action})
            for resolution,pixels in (('native_1080',frame),('letterbox_640',letterbox(frame))):
                result=detectors[resolution].observe(pixels)
                if result.crops is None:raise ValueError('Annotated frame has no usable crop geometry')
                meta={'split':SPLITS[clip],'domain':'camera','source':clip,'frame':index,'timestamp':timestamp,
                      'parent_id':clip,'quality':result.quality,'resolution':resolution,'action':action,
                      'angle':'lateral' if clip==CLIPS[0] else 'oblique' if clip==CLIPS[1] else 'low_camera',
                      'subject_id':'p01','capture_group':'p01_20261013','eye_boxes':result.boxes[:2]}
                for eye,label in enumerate(eye_labels):
                    if label!='Unknown':add(result.crops[eye],{**meta,'label':label,'eye_index':eye},'eye')
                if yawn_label!='Unknown':add(result.crops[2],{**meta,'label':yawn_label},'yawn')
        cap.release()
    dataset={'schema_version':1,'kind':'driver_monitor_multiview','records':records,
             'runtime_specs':{name:base['classifiers'][name] for name in ('eye','yawn')},'sources':sources,
             'annotation_method':'Coding-agent visual review of source, face and both eye crops; user confirmed actions; ambiguous eyes excluded.',
             'test_clip':CLIPS[1],'selection_domain':'retained_static_validation_only',
             'subject_independence':False,'camera_validation_pending':True,'event_acceptance_measured':False,
             'native_and_letterbox_are_correlated':True,
             'letterbox_policy':'1920x1080 -> 640x360 preserving aspect, padded to 640x480. Not a proven pixel match to live driver output.'}
    (destination/'dataset.json').write_text(json.dumps(dataset,indent=2),encoding='utf-8')
    (destination/'base_manifest.json').write_text(json.dumps(base,indent=2),encoding='utf-8')
    settings=asdict(config);settings.pop('monitor',None);settings['monitor']=asdict(config.monitor)
    (destination/'runtime_settings.json').write_text(json.dumps(settings,default=str,indent=2),encoding='utf-8')
    with (ROOT/'data_collection/multiview_20261013/annotations.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(annotations[0]));writer.writeheader();writer.writerows(annotations)
    for name in ('eye','yawn'):
        checkpoint=artifact_path(config.manifest,base['classifiers'][name]['artifacts']['torch'])
        shutil.copy2(checkpoint,destination/f'baseline_{name}.pt')
    support=destination/'support/driver_monitor';support.mkdir(parents=True)
    for path in (ROOT/'driver_monitor').glob('*.py'):shutil.copy2(path,support/path.name)
    shutil.copy2(ROOT/'tools/kaggle_multiview_training.py',destination/'kaggle_multiview_training.py')
    checksums={p.relative_to(destination).as_posix():sha256(p) for p in destination.rglob('*') if p.is_file()}
    bundle={'kind':'driver_monitor_multiview','schema_version':1,'checksums':checksums,
            'training_authorized':True,'checkpoints':{name:f'baseline_{name}.pt' for name in ('eye','yawn')}}
    (destination/'bundle.json').write_text(json.dumps(bundle,indent=2),encoding='utf-8')
    archive=destination.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in destination.rglob('*'):
            if path.is_file():z.write(path,path.relative_to(destination).as_posix())
    summary={'archive':str(archive),'sha256':sha256(archive),'records':len(records),
             'counts':dict(Counter(f"{r['task']}/{r['split']}/{r['domain']}/{r['label']}" for r in records)),
             'camera_unknown_labels_excluded':sum(x=='Unknown' for r in annotations for x in (r['left_eye'],r['right_eye'],r['yawn']))}
    (ROOT/'data_collection/multiview_20261013/bundle_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':build()
