"""Replay known no-glasses RGB clips and compare real runtime outputs, not mocks."""
import csv
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    import numpy as np
    import onnxruntime as ort
    from driver_monitor.config import load_config
    from driver_monitor.runtime import run
    from driver_monitor.models import sha256,read_manifest
    from driver_monitor.eyewear import EyewearModel
    from driver_monitor.capture import Capture
    from driver_monitor.vision import Vision
    out=ROOT/'reports/glasses_adaptation_20261013/automatic_routing';out.mkdir(parents=True,exist_ok=True)
    selector=EyewearModel(ROOT/'models/eyewear_selector/manifest.json')
    sample=np.load(ROOT/'.cache/eyewear_celeba/parity_inputs.npz')
    p=np.concatenate([selector.model.run(None,{selector.input_name:x[None]})[0] for x in sample['inputs']])
    delta=float(np.max(np.abs(p-sample['probabilities'])))
    parity={'samples':len(p),'gpu_torch_vs_pc_onnx_max_delta':delta,
            'argmax_mismatches':int(np.sum(p.argmax(1)!=sample['probabilities'].argmax(1))),
            'onnxruntime':ort.__version__}
    assert delta<1e-4 and parity['argmax_mismatches']==0
    videos=[Path(r'C:\Users\P1 Gen 5\Pictures\Camera Roll')/name for name in
            ('WIN_20261013_17_05_46_Pro.mp4','WIN_20261013_17_07_01_Pro.mp4','WIN_20261013_17_07_34_Pro.mp4')]
    videos.append(ROOT/'data_collection/eye_medium/steady_open/20261013T015318_188531Z_eye.avi')
    compared=[]
    for index,video in enumerate(videos):
        if not video.is_file():continue
        records={};performance={};folders={};event_files={}
        for mode in ('original','automatic'):
            directory=out/f'clip_{index:02d}'/mode;folders[mode]=directory
            directory.mkdir(parents=True,exist_ok=True)
            before=set(directory.glob('*.csv'))
            config=load_config(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml',headless=True,
                               log_dir=directory,auto_glasses=mode=='automatic')
            performance[mode]=run(config,str(video))
            created=set(directory.glob('*.csv'))-before;assert len(created)==1
            new_csv=created.pop();event_files[mode]=new_csv.with_suffix('.jsonl')
            with new_csv.open(encoding='utf-8',newline='') as stream:records[mode]=list(csv.DictReader(stream))
        rows=records['automatic'];original=records['original'];assert len(rows)==len(original)
        keys=('timestamp','state','alert','reasons','quality','eye_quality','left_closed','right_closed',
              'yawn_probability','yawn_raw_probability','yawn_state','yawn_count','blink_total','left_eye_events','right_eye_events')
        differences={key:sum(a[key]!=b[key] for a,b in zip(original,rows)) for key in keys}
        events=[]
        events.extend(json.loads(line) for line in event_files['automatic'].read_text(encoding='utf-8').splitlines())
        switches=[e for e in events if e.get('event')=='eye_model_changed' and e.get('branch')=='glasses']
        scores=[e['quality_metrics']['eyewear_probability'] for e in events if e.get('event')=='status'
                and e.get('quality_metrics',{}).get('eyewear_probability') is not None]
        compared.append({'source':str(video),'sha256':sha256(video),'frames':len(rows),'differences':differences,
                         'wrong_specialist_switches':len(switches),'max_reported_p_glasses':max(scores) if scores else None,
                         'performance':performance})
        print(json.dumps({k:v for k,v in compared[-1].items() if k not in ('performance','source','sha256')},indent=2),flush=True)
    config=load_config(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml')
    manifest=read_manifest(config.manifest)
    report={'parity':parity,'known_no_glasses_rgb_replays':compared,'glasses_rgb_camera_acceptance':False,
            'base_config_fingerprint':config.fingerprint(),'base_eye_sha256':manifest['classifiers']['eye']['artifacts']['onnx']['sha256'],
            'yawn_sha256':manifest['classifiers']['yawn']['artifacts']['onnx']['sha256'],
            'routing_enabled_by_explicit_option':True,
            'passed':bool(compared) and all(v['wrong_specialist_switches']==0 and not any(v['differences'].values()) for v in compared),
            'limits':'Known one-person development videos, offline headless replay. Not a guarantee for other drivers/cameras or live performance.'}
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'clips':len(compared),'parity':parity},indent=2))
    selector.close()
    if not report['passed']:raise RuntimeError('No-glasses regression/routing evidence failed; keep automatic mode experimental')


if __name__=='__main__':main()
