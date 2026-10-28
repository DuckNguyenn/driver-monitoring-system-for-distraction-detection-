"""Verify a glasses candidate in the actual PC inference/runtime environment."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    import cv2
    import numpy as np
    import torch
    import onnxruntime
    from driver_monitor.models import Classifier,read_manifest,sha256
    from tools.kaggle_glasses_training import metrics
    folder=ROOT/'models/eye_glasses_adapted';manifest=folder/'manifest.json'
    bundle=ROOT/'kaggle_upload/glasses_adaptation_20261013'
    data=json.loads((bundle/'dataset.json').read_text(encoding='utf-8'))
    rows=[r for r in data['records'] if r['split']=='test']
    report=json.loads((folder/'evaluation.json').read_text(encoding='utf-8'))
    model=Classifier(manifest,'eye','onnx');reference=Classifier(manifest,'eye','torch')
    probabilities=[];deltas=[];label_differences=0
    parity_indexes=set(np.linspace(0,len(rows)-1,32,dtype=int))
    for index,row in enumerate(rows):
        image=cv2.imread(str(bundle/row['file']));assert image is not None
        p=model.predict(image);probabilities.append([p['Closed'],p['Open']])
        if index in parity_indexes:
            q=reference.predict(image)
            deltas.append(max(abs(p[label]-q[label]) for label in p))
            label_differences+=max(p,key=p.get)!=max(q,key=q.get)
    measured=metrics(rows,np.asarray(probabilities))
    for group,value in measured.items():
        assert value['confusion_matrix']==report['test']['candidate'][group]['confusion_matrix']
        assert value['confidence_and_quality_gate']['confusion_matrix_with_unknown']==report['test']['candidate'][group]['confidence_and_quality_gate']['confusion_matrix_with_unknown']
    assert max(deltas)<=1e-4 and label_differences==0
    verification={'torch':torch.__version__,'onnxruntime':onnxruntime.__version__,'parity_samples':len(deltas),
                  'max_probability_delta':max(deltas),'label_mismatches':label_differences,'passed':True,
                  'manifest_sha256':sha256(manifest),'pc_metrics':measured,'camera_rgb_glasses_acceptance':False}
    model.close();reference.close()
    # Yawn/detector files and runtime thresholds still resolve from the existing installation.
    from driver_monitor.config import load_config
    from driver_monitor.runtime import run
    settings=load_config(folder/'runtime.yaml',headless=True,max_frames=20,
                         log_dir=ROOT/'reports/glasses_adaptation_20261013/integration_logs')
    old=load_config(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml')
    assert settings.monitor==old.monitor
    assert read_manifest(manifest)['classifiers']['yawn']['artifacts']['onnx']['sha256']==read_manifest(old.manifest)['classifiers']['yawn']['artifacts']['onnx']['sha256']
    video=Path(r'C:\Users\P1 Gen 5\Pictures\Camera Roll\WIN_20261013_17_07_01_Pro.mp4')
    verification['integration']=run(settings,str(video))
    assert verification['integration']['frames']==20 and verification['integration']['fault'] is None
    verification['incumbent_eye_preserved']=sha256(ROOT/'models/eye_refined_v4/best_eye.onnx')=='165e8cf94e0283135d6f4cb1c799261c47c5b6aca4501cbc43b98a7d66e5e6ed'
    assert verification['incumbent_eye_preserved']
    target=ROOT/'reports/glasses_adaptation_20261013/pc_verification.json'
    target.write_text(json.dumps(verification,indent=2),encoding='utf-8')
    state_path=ROOT/'kaggle_upload/glasses_cloud/latest.json'
    state=json.loads(state_path.read_text(encoding='utf-8'));state.update(status='complete',pc_parity_verified=True,promotion_status='experimental_only')
    state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in verification.items() if k not in ('pc_metrics','integration')},indent=2))


if __name__=='__main__':main()
