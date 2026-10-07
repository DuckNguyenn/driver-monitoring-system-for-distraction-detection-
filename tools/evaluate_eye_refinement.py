"""Pixel-level eye evaluation/parity after locking the candidate checkpoint."""
import argparse
import json
from pathlib import Path
import sys
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from driver_monitor.config import load_config
from driver_monitor.models import Classifier,prepare_rgb,sha256
from driver_monitor.vision import Vision
from driver_monitor.evaluation import classification_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,default=ROOT/'models/eye_refined_v4/manifest.json')
    parser.add_argument('--records',type=Path,default=ROOT/'.cache/eye_refinement_v4/records.json')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/eye_refinement_pixels.json')
    args = parser.parse_args()
    config = load_config(ROOT/'configs/camera_pc.yaml',manifest=args.manifest)
    provenance = json.loads(args.records.read_text())
    evaluation = json.loads((args.manifest.parent/'evaluation.json').read_text())
    excluded = set(evaluation['provenance']['cross_split_duplicate_images_excluded'])
    rows = [r for r in provenance['records'] if r['split'] == 'test' and r['variant'] == 'base' and r['path'] not in excluded]
    baseline = Classifier(ROOT/'models/manifest.json','eye','onnx')
    model = Classifier(config.manifest,'eye','onnx')
    reference = Classifier(config.manifest,'eye','torch')
    predictions,maximum_error,agreement = [],0.,0
    current_path, image, crops = None,None,None
    try:
        for row in rows:
            if row['path'] != current_path:
                current_path = row['path']
                path = ROOT/current_path
                if sha256(path) != row['sha256']:
                    raise ValueError('Reviewed source pixels changed')
                image = cv2.imread(str(path))
                result = Vision(config).observe(image) if row['source'] == 'roi' else None
                if result and result.quality != 'usable':
                    raise ValueError('Crop quality/config changed')
                crops = result.crops if result else None
            crop = crops[row['eye_index']] if crops is not None else image
            old,new,expected = baseline.predict(crop),model.predict(crop),reference.predict(crop)
            maximum_error = max(maximum_error,abs(new['Closed']-expected['Closed']))
            agreement += max(new,key=new.get) == max(expected,key=expected.get)
            predictions.append({'path':row['path'],'sha256':row['sha256'],'source':row['source'],
                'dataset':row.get('dataset','legacy'),'label':row['label'],'eye_index':row.get('eye_index'),
                'baseline_closed':old['Closed'],'candidate_closed':new['Closed']})
    finally:
        for classifier in (baseline,model,reference):classifier.close()
    summary = {}
    for dataset in ('legacy','genki','yawn_faces','cew'):
        selected = [r for r in predictions if r['dataset'] == dataset]
        summary[dataset] = {}
        for variant in ('baseline','candidate'):
            p = [r[f'{variant}_closed'] for r in selected]
            labels = [r['label'] for r in selected]
            metric = classification_metrics(labels,['Closed' if v >= .5 else 'Open' for v in p],['Closed','Open'])
            metric['false_closed_ge_080'] = sum(r['label']=='Open' and r[f'{variant}_closed']>=.8 for r in selected)
            metric['Closed_recall_ge_080'] = sum(r['label']=='Closed' and r[f'{variant}_closed']>=.8 for r in selected)/max(1,labels.count('Closed'))
            summary[dataset][variant] = metric
    report = {'type':'eye_classifier_actual_pixels_after_export','manifest_sha256':sha256(config.manifest),
        'records_sha256':sha256(args.records),'summary':summary,
        'parity':{'maximum_probability_error':maximum_error,'label_agreement':agreement/max(1,len(rows))},
        'scope':'Static development audit; known bug is in train; human label audit and independent natural driver-video acceptance pending',
        'predictions':predictions}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'predictions'}),flush=True)
    if maximum_error > .001 or agreement != len(rows):
        raise AssertionError('Torch/ONNX eye parity failed')


if __name__ == '__main__':
    main()
