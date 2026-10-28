"""Record clean RGB glasses data with source timestamps and collection metadata."""
from pathlib import Path
import argparse
import csv
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='1')
    parser.add_argument('--subject-id',required=True)
    parser.add_argument('--capture-group',required=True)
    parser.add_argument('--split',choices=('train','val','test'),required=True)
    parser.add_argument('--lighting',default='indoor_diffuse')
    parser.add_argument('--distance',choices=('near','medium','far'),default='medium')
    parser.add_argument('--duration',type=float,default=75)
    parser.add_argument('--config',default=str(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml'))
    parser.add_argument('--output-dir',type=Path,default=ROOT/'data_collection/eye_glasses/videos')
    parser.add_argument('--headless',action='store_true')
    args=parser.parse_args(argv)
    if args.duration<=0:parser.error('duration must be positive')
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    before=set(output.glob('*.avi'))
    from tools import test_original_model as recorder
    original_draw=recorder.draw
    protocol=[(0,15,'Keep both eyes open; blink naturally'),(15,30,'Wink eye 1 five times; rest between winks'),
              (30,45,'Wink eye 2 five times; rest between winks'),(45,60,'Blink both five times; close both for 2 seconds'),
              (60,75,'Eyes open; turn head slightly to vary reflections')]
    def draw(*values,**kwargs):
        original_draw(*values,**kwargs)
        preview=values[0];elapsed=values[4]
        prompt=next((text for start,end,text in protocol if start<=elapsed<end),'Eyes open; finish when ready')
        import cv2
        cv2.rectangle(preview,(0,preview.shape[0]-57),(preview.shape[1],preview.shape[0]-27),(20,20,20),-1)
        cv2.putText(preview,prompt,(8,preview.shape[0]-37),cv2.FONT_HERSHEY_SIMPLEX,.40,(240,240,240),1,cv2.LINE_AA)
    recorder.draw=draw
    options=['--name','eye','--use-config-model','--config',args.config,'--backend','onnx','--source',args.source,
             '--inspect-model','--record','--duration',str(args.duration),'--output-dir',str(output)]
    if args.headless:options.append('--headless')
    print('Wear clear prescription glasses. Prompts are collection guidance, never automatic eye labels.',flush=True)
    try:recorder.main(options)
    finally:recorder.draw=original_draw
    created=set(output.glob('*.avi'))-before
    if len(created)!=1:raise RuntimeError('Expected exactly one new recording')
    video=created.pop();meta_path=video.with_suffix('.metadata.json')
    meta=json.loads(meta_path.read_text(encoding='utf-8'))
    from driver_monitor.config import load_config
    settings=load_config(args.config)
    meta['vision_settings']={key:getattr(settings,key) for key in (
        'detector_size','detector_confidence','driver_roi','eye_width_ratio','eye_height_ratio','face_margin',
        'min_face_size','min_eye_width','min_brightness','min_sharpness','min_eye_sharpness','max_overexposed_ratio',
        'eye_motion_window_seconds','eye_motion_settle_seconds','eye_motion_max_shift_ratio','eye_motion_max_roll_degrees','rotation_degrees')}
    meta['collection']={'subject_id':args.subject_id,'capture_group':args.capture_group,'split':args.split,
                        'glasses':True,'glasses_type':'prescription_clear','lighting':args.lighting,'distance':args.distance}
    meta['protocol_prompts']=[{'start':start,'end':end,'text':text} for start,end,text in protocol]
    meta.update(training_allowed=False,eye_labels_require_review=True)
    meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved glasses RGB:',video,flush=True)
    print('Review:',f'python tools/annotate_eye_glasses.py --video "{video}"',flush=True)


if __name__=='__main__':main()
