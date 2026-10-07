"""Complete-runtime replays of visually labelled real face pixels.

Still frames repeated in lossless videos test model/logic integration. They
are not natural driver wink clips or independent event-accuracy evidence.
"""
import csv
import json
import sys
from dataclasses import replace
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from driver_monitor.config import load_config
from driver_monitor.models import Classifier,sha256
from driver_monitor.runtime import run
from driver_monitor.vision import Vision


def replay(config, source_image, label, folder):
    image = cv2.imread(str(source_image))
    h,w = image.shape[:2]
    image = cv2.copyMakeBorder(image,0,h%2,0,w%2,cv2.BORDER_REPLICATE)
    h,w = image.shape[:2]
    video = ROOT/'reports'/f'eye_{label}_fixture.avi'
    writer = cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'FFV1'),15,(w,h))
    if not writer.isOpened():raise RuntimeError('Lossless video writer unavailable')
    for frame in range(45):writer.write(image)
    writer.release()
    current = replace(config,headless=True,log_dir=ROOT/'reports/eye_classifier_replay'/folder)
    summary = run(current,video)
    log = max(current.log_dir.glob('*.csv'),key=lambda p:p.stat().st_mtime)
    with log.open() as stream:rows = list(csv.DictReader(stream))
    return {'summary':summary,'video_sha256':sha256(video),'source_sha256':sha256(source_image),
        'frame_log':log.relative_to(ROOT).as_posix(),'frame_log_sha256':sha256(log),
        'alert_frames':sum(r['alert']=='1' for r in rows),
        'both_closed_frames':sum(r['eye_closed']=='1' for r in rows),
        'usable_frames':sum(r['quality']=='usable' for r in rows)}


def main():
    config = load_config(ROOT/'configs/camera_pc.yaml',headless=True)
    source = ROOT/'tests/fixtures/eyes/open_narrow_face.jpg'
    baseline = replace(config,manifest=ROOT/'models/smile_refined/manifest.json')
    results = {'original_open_face':replay(baseline,source,'open','original'),
               'refined_open_face':replay(config,source,'open','refined')}
    review = json.loads((ROOT/'data_reviews/eye_roi_labels_v2.json').read_text())['records']
    closed = ROOT/next(r['path'] for r in review if r['id']==201)
    results['refined_true_closed_face'] = replay(config,closed,'closed','true_closed')
    old,new = Classifier(baseline.manifest,'eye','onnx'),Classifier(config.manifest,'eye','onnx')
    crops = Vision(config).observe(cv2.imread(str(source))).crops
    try:
        diagnostic = {'baseline_p_closed':[old.predict(c)['Closed'] for c in crops[:2]],
                      'candidate_p_closed':[new.predict(c)['Closed'] for c in crops[:2]]}
    finally:
        old.close();new.close()
    report = {'type':'derived_real_face_eye_replay','manifest_sha256':sha256(config.manifest),
        'diagnostic':diagnostic,'results':results,
        'scope':'Known Open failure added to training; static derived videos test integration, not natural wink accuracy'}
    path = ROOT/'reports/eye_classifier_replay.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert results['original_open_face']['alert_frames']>0,'Original model did not reproduce false closure'
    assert results['refined_open_face']['usable_frames']==45,'Quality gate hid the eye-classifier error'
    assert results['refined_open_face']['alert_frames']==0
    assert results['refined_open_face']['both_closed_frames']==0
    assert results['refined_true_closed_face']['alert_frames']>0,'True bilateral closure was lost'
    print(json.dumps({'diagnostic':diagnostic,'alerts':{k:v['alert_frames'] for k,v in results.items()}}))


if __name__ == '__main__':
    main()
