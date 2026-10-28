"""Build a locked subject split of MRL plus retained RGB rehearsal crops."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import shutil
import sys
import zipfile
import argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-bundle',type=Path,default=ROOT/'kaggle_upload/glasses_adaptation_20261013')
    parser.add_argument('--rgb-supplement',type=Path,help='Reviewed RGB eye supplement folder with train/val/test subjects')
    parser.add_argument('--config',type=Path,default=ROOT/'models/yawn_kaggle_near_medium/runtime.yaml')
    parser.add_argument('--starting-eye-manifest',type=Path,help='Optional separate glasses checkpoint to continue adapting')
    args=parser.parse_args(argv)
    import cv2
    import numpy as np
    from driver_monitor.eye_glasses import mrl_annotation,sample_mrl
    from driver_monitor.glasses_training import subject_split,validate_subjects,validate_rgb_subjects,sampling_mass
    from driver_monitor.models import read_manifest,prepare_rgb,sha256,artifact_path
    from driver_monitor.config import load_config
    from dataclasses import asdict
    destination=args.output_bundle.resolve()
    if destination.exists() and any(destination.iterdir()):raise ValueError('Bundle already exists; do not overwrite a locked run')
    config=load_config(args.config)
    manifest=read_manifest(config.manifest);spec=manifest['classifiers']['eye']
    starting_manifest=config.manifest;starting_spec=spec
    if args.starting_eye_manifest:
        starting_manifest=args.starting_eye_manifest.resolve();starting_spec=read_manifest(starting_manifest)['classifiers']['eye']
        if any(starting_spec[key]!=spec[key] for key in ('classes','input_size','preprocessing')):
            raise ValueError('Starting eye checkpoint has different preprocessing/classes')
    rgb_extra=None
    if args.rgb_supplement:
        rgb_extra=json.loads((args.rgb_supplement/'dataset.json').read_text(encoding='utf-8'))
        if (rgb_extra.get('kind')!='driver_monitor_eye_rgb_supplement' or rgb_extra.get('automatic_eye_labels') is not False
                or rgb_extra.get('subject_split_verified') is not True):
            raise ValueError('Expected a manually reviewed RGB glasses supplement')
        a=rgb_extra['runtime_spec']
        if any(a[key]!=spec[key] for key in ('classes','input_size','preprocessing')):
            raise ValueError('RGB supplement preprocessing differs from current eye runtime')
        validate_rgb_subjects(rgb_extra['records'],require_complete=True)
    destination.mkdir(parents=True,exist_ok=True)
    records=[];owners={};excluded=[]
    def add(raw,image,metadata):
        raw_hash=hashlib.sha256(raw).hexdigest();input_hash=hashlib.sha256(prepare_rgb(image,spec).tobytes()).hexdigest()
        previous=owners.get(input_hash)
        if previous is not None:
            if previous!=metadata['label'] or any(r['input_sha256']==input_hash and r['split']!=metadata['split'] for r in records):
                raise ValueError('Duplicate eye input crosses split or conflicting label')
            excluded.append({**metadata,'reason':'duplicate_input_same_split'})
            return False
        owners[input_hash]=metadata['label']
        file=f'native/{len(records):06d}.png';path=destination/file
        path.parent.mkdir(parents=True,exist_ok=True)
        if not cv2.imwrite(str(path),image):raise OSError('Cannot write crop')
        records.append({**metadata,'file':file,'sha256':sha256(path),'source_sha256':raw_hash,
                        'input_sha256':input_hash,'quality':metadata.get('quality','usable'),'native_shape':list(image.shape)})
        return True
    archive=ROOT/'.cache/mrl_glasses/kaggle/mrl-eye-dataset.zip'
    with zipfile.ZipFile(archive) as zipped:
        catalog=[{**a,'split':subject_split(a['subject'])} for member in zipped.namelist() if (a:=mrl_annotation(member)) is not None]
        # Heldout ownership is protected before retaining training images.
        for split,limit in (('test',256),('val',256),('train',512)):
            subset=[r for r in catalog if r['split']==split]
            selected=sample_mrl(subset,limit)
            for row in selected:
                raw=zipped.read(row['member']);image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
                assert image is not None
                add(raw,image,{**row,'domain':'mrl','source':'mrl_glasses' if row['glasses'] else 'mrl_no_glasses',
                               'resolution':'IR_native','new_glasses_camera':False})
    rgb_root=ROOT/'kaggle_upload/multiview_20261013'
    rgb_data=json.loads((rgb_root/'dataset.json').read_text(encoding='utf-8'))
    for split in ('test','val','train'):
        for row in rgb_data['records']:
            if row['task']!='eye' or row['split']!=split:continue
            path=rgb_root/row['file'];assert sha256(path)==row['sha256']
            raw=path.read_bytes();image=cv2.imread(str(path))
            add(raw,image,{'domain':'rgb_rehearsal','source':row['source'],'split':split,'label':row['label'],
                           'subject':row.get('subject_id'),'glasses':None,'reflection':None,'lighting':None,'sensor':None,
                           'resolution':row.get('resolution','original'),'new_glasses_camera':False})
    if rgb_extra:
        extra_root=args.rgb_supplement.resolve()
        for row in rgb_extra['records']:
            path=(extra_root/row['file']).resolve()
            if not path.is_relative_to(extra_root) or sha256(path)!=row['sha256']:
                raise ValueError('RGB supplement crop path/checksum changed')
            image=cv2.imread(str(path))
            if image is None or hashlib.sha256(prepare_rgb(image,spec).tobytes()).hexdigest()!=row['input_sha256']:
                raise ValueError('RGB supplement pixels/preprocessing changed')
            add(path.read_bytes(),image,{k:v for k,v in row.items() if k not in ('file','sha256','input_sha256','native_shape')})
    validate_subjects(records)
    if rgb_extra:validate_rgb_subjects(records,require_complete=True)
    data={'kind':'driver_monitor_glasses_adaptation','classes':['Closed','Open'],'records':records,
          'runtime_spec':spec,'mrl_subject_split':{s:sorted({r['subject'] for r in records if r['domain']=='mrl' and r['split']==s}) for s in ('train','val','test')},
          'mrl_original_checkpoint_membership':'unknown','fresh_subject_generalization_proven':False,
          'prior_mrl_audit_seen':True,'split_scope':'subject-disjoint for this fine-tuning stage only',
          'new_rgb_glasses_camera_present':rgb_extra is not None,'live_acceptance_pending':True,
          'rgb_supplement_sha256':None if rgb_extra is None else sha256(args.rgb_supplement/'dataset.json'),
          'rgb_sources':[] if rgb_extra is None else rgb_extra['sources'],
          'sampling_mass':sampling_mass([r for r in records if r['split']=='train']),
          'archive_sha256':sha256(archive),'duplicates_excluded':excluded}
    (destination/'dataset.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    shutil.copy2(artifact_path(starting_manifest,starting_spec['artifacts']['torch']),destination/'baseline_eye.pt')
    # New eye artifacts stay separate; refer to the chosen base profile's real yawn/detector.
    def model_reference(original):
        model_root=(ROOT/'models').resolve()
        if not original.is_relative_to(model_root):raise ValueError('Export references require existing models inside the project models folder')
        return '../'+original.relative_to(model_root).as_posix()
    detector_path=artifact_path(config.manifest,manifest['detector'])
    manifest['detector']['file']=model_reference(detector_path)
    for backend,artifact in manifest['classifiers']['yawn']['artifacts'].items():
        original=artifact_path(config.manifest,artifact)
        artifact['file']=model_reference(original)
    (destination/'base_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    settings=asdict(config);settings.update(manifest='manifest.json',log_dir='../../logs')
    (destination/'runtime_settings.json').write_text(json.dumps(settings,default=str,indent=2),encoding='utf-8')
    support=destination/'support/driver_monitor';support.mkdir(parents=True)
    for name in ('models.py','multiview_learning.py','glasses_training.py'):
        shutil.copy2(ROOT/'driver_monitor'/name,support/name)
    (support/'__init__.py').write_text('',encoding='utf-8')
    shutil.copy2(ROOT/'tools/kaggle_glasses_training.py',destination/'kaggle_glasses_training.py')
    checks={p.relative_to(destination).as_posix():sha256(p) for p in destination.rglob('*') if p.is_file()}
    (destination/'bundle.json').write_text(json.dumps({'kind':data['kind'],'checkpoint':'baseline_eye.pt','checksums':checks},indent=2),encoding='utf-8')
    result=destination.with_suffix('.zip')
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in destination.rglob('*'):
            if path.is_file():output.write(path,path.relative_to(destination).as_posix())
    summary={'archive':str(result),'sha256':sha256(result),'records':len(records),
             'counts':{str(k):v for k,v in Counter((r['split'],r['domain'],r['glasses'],r['label']) for r in records).items()},
             'new_rgb_glasses_camera_present':rgb_extra is not None,'stage_subject_split':data['mrl_subject_split'],'model_promoted':False}
    out=ROOT/'reports/glasses_adaptation_20261013';out.mkdir(parents=True,exist_ok=True)
    # Completed run evidence stays immutable; later bundles have separate summaries.
    summary_file='bundle.json' if destination.name=='glasses_adaptation_20261013' else destination.name+'.bundle.json'
    (out/summary_file).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
