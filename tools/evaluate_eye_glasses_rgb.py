"""Compare original/specialist eye classifiers and automatic routing on reviewed RGB."""
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def checked_dataset(folder,config,split):
    import cv2
    from driver_monitor.models import read_manifest,sha256,prepare_rgb
    from driver_monitor.glasses_training import validate_rgb_subjects
    folder=Path(folder).resolve();data=json.loads((folder/'dataset.json').read_text(encoding='utf-8'))
    if data.get('kind')!='driver_monitor_eye_rgb_supplement' or data.get('automatic_eye_labels') is not False:
        raise ValueError('Prepare a manually reviewed RGB glasses dataset first')
    validate_rgb_subjects(data['records'])
    spec=read_manifest(config.manifest)['classifiers']['eye']
    if any(data['runtime_spec'][key]!=spec[key] for key in ('classes','input_size','preprocessing')):
        raise ValueError('Dataset preprocessing differs from current eye runtime')
    rows=[r for r in data['records'] if r['split']==split]
    if not rows:raise ValueError('No reviewed RGB glasses rows in '+split)
    for row in rows:
        if type(row.get('frame')) is not int or row['frame']<0 or row.get('eye_index') not in (0,1):
            raise ValueError('Invalid reviewed frame or eye index')
        path=(folder/row['file']).resolve()
        if not path.is_relative_to(folder) or sha256(path)!=row['sha256']:raise ValueError('Crop file/checksum changed')
        image=cv2.imread(str(path))
        if image is None or hashlib.sha256(prepare_rgb(image,spec).tobytes()).hexdigest()!=row['input_sha256']:
            raise ValueError('Crop input pixels changed')
    return data,rows


def automatic_guesses(rows,records,threshold):
    from driver_monitor.core import probabilities
    result=[]
    for row in rows:
        if not 0<=row['frame']<len(records) or row['eye_index'] not in (0,1):raise ValueError('Reviewed frame/eye not present in replay')
        record=records[row['frame']];observation=record['observation']
        if observation.get('quality')!='usable' or observation.get('eye_quality')!='usable':
            result.append('UNKNOWN');continue
        name=('left_eye','right_eye')[row['eye_index']]
        values=probabilities(observation.get(name),('Closed','Open'))
        if values is None:result.append('UNKNOWN')
        elif values['closed']>=threshold:result.append('Closed')
        elif values['open']>=threshold:result.append('Open')
        else:result.append('UNKNOWN')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=ROOT/'data_collection/eye_glasses/rgb_supplement')
    parser.add_argument('--config',type=Path,default=ROOT/'models/yawn_kaggle_near_medium/runtime.yaml')
    parser.add_argument('--candidate-manifest',type=Path,default=ROOT/'models/eye_glasses_adapted/manifest.json')
    parser.add_argument('--split',choices=('train','val','test'),default='test')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--skip-replay',action='store_true',help='Static crop metrics only; no automatic-routing claim')
    args=parser.parse_args(argv)
    import cv2
    import numpy as np
    from driver_monitor.models import Classifier,read_manifest,sha256,artifact_path
    from driver_monitor.config import load_config
    from driver_monitor.multiview_learning import evaluate,matrix_metrics
    config=load_config(args.config);data,rows=checked_dataset(args.data,config,args.split)
    output=(args.output or ROOT/'reports/glasses_rgb_evaluation'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')).resolve()
    if output.exists() and any(output.iterdir()):raise ValueError('Evaluation output exists; preserve previous evidence')
    output.mkdir(parents=True,exist_ok=True)
    models=[];scores={};identities={}
    try:
        for name,path in (('original',config.manifest),('specialist',args.candidate_manifest)):
            spec=read_manifest(path)['classifiers']['eye']
            if any(spec[key]!=data['runtime_spec'][key] for key in ('classes','input_size','preprocessing')):
                raise ValueError('Candidate changes preprocessing or class order')
            identities[name]=sha256(artifact_path(path,spec['artifacts']['onnx']))
            model=Classifier(path,'eye','onnx',config.cpu_threads);models.append(model)
            p=[]
            for row in rows:
                prediction={k.casefold():v for k,v in model.predict(cv2.imread(str(args.data/row['file']))).items()}
                p.append([prediction['closed'],prediction['open']])
            scores[name]=np.asarray(p,np.float32)
    finally:
        for model in models:model.close()
    report={'split':args.split,'dataset_sha256':sha256(args.data/'dataset.json'),'samples':len(rows),
            'static':{name:evaluate(rows,p,'eye') for name,p in scores.items()},'model_sha256':identities,
            'automatic':None,'natural_blink_accuracy':None,'event_accuracy':None,
            'test_used_for_model_selection':False,'models_modified':False,
            'limits':'Reviewed eye crops are correlated frames; image F1 does not establish blink accuracy or false alerts/hour.'}
    with (output/'predictions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['source','frame','eye_index','subject','label','quality','original_p_closed','specialist_p_closed'])
        for row,a,b in zip(rows,scores['original'],scores['specialist']):
            writer.writerow([row.get(k) for k in ('source','frame','eye_index','subject','label','quality')]+[float(a[0]),float(b[0])])
    if not args.skip_replay:
        from driver_monitor.runtime import run
        from driver_monitor.eye_collection import recorded_times
        clips=[];truth=[];predicted=[]
        for source in data['sources']:
            if source['split']!=args.split:continue
            video=Path(source['video']);metadata,times=recorded_times(video)
            if metadata['video_sha256']!=source['video_sha256']:raise ValueError('Reviewed source video changed')
            selected=[r for r in rows if r['source']==video.stem]
            if not selected:continue
            cfg=load_config(args.config,headless=True,auto_glasses=True,glasses_eye_manifest=args.candidate_manifest,
                            log_dir=output/'replay_logs'/video.stem,**metadata.get('vision_settings',{}))
            cfg.serial_port=None  # An evaluation video must never command a physical buzzer.
            records=[]
            observer=SimpleNamespace(start=lambda *_:None,record=lambda record,*_:records.append(record),fault=lambda *_:None,end=lambda *_:None,wants_preview=lambda:False)
            summary=run(cfg,str(video),observer=observer)
            if len(records)!=summary['frames']:raise ValueError('Replay record/frame count mismatch')
            guesses=automatic_guesses(selected,records,cfg.monitor.eye_confidence)
            metric=matrix_metrics([r['label'] for r in selected],guesses,['Closed','Open'])
            branch_counts={branch:sum(r.get('quality_metrics',{}).get('eye_model_branch')==branch for r in records) for branch in ('original','glasses')}
            clips.append({'source':str(video),'samples':len(selected),'metrics':metric,'branch_frame_counts':branch_counts,'summary':summary})
            truth.extend(r['label'] for r in selected);predicted.extend(guesses)
        if clips:report['automatic']={'clips':clips,'metrics':matrix_metrics(truth,predicted,['Closed','Open'])}
    (output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,(name,metric) in zip(axes,[('Mắt gốc',report['static']['original']['confidence_and_quality_gate']),
                                  ('Mắt chuyên kính',report['static']['specialist']['confidence_and_quality_gate']),
                                  ('Tự chuyển model',report['automatic']['metrics'] if report['automatic'] else None)]):
        if metric is None:ax.axis('off');ax.set_title(name+' · chưa đo');continue
        matrix=np.asarray(metric['confusion_matrix_with_unknown']);ax.imshow(matrix,cmap='Blues')
        ax.set_xticks([0,1,2],['Nhắm','Mở','UNKNOWN']);ax.set_yticks([0,1],['Nhắm','Mở']);ax.set_title(name)
        ax.set_xlabel('Dự đoán');ax.set_ylabel('Thực tế')
        for (i,j),n in np.ndenumerate(matrix):ax.text(j,i,str(n),ha='center',va='center',color='white' if n>matrix.max()/2 else 'black')
    fig.tight_layout();fig.savefig(output/'comparison_matrix.png',dpi=165);plt.close(fig)
    print(json.dumps({'output':str(output),'samples':len(rows),'static_F1':{k:v['macro_f1'] for k,v in report['static'].items()},
                      'automatic_measured':report['automatic'] is not None,'natural_blink_accuracy':None},indent=2))
    return report


if __name__=='__main__':main()
