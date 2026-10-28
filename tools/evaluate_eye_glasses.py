"""Audit fixed eye checkpoints on MRL images; no training or threshold tuning."""
from pathlib import Path
from collections import Counter
import argparse
import csv
import hashlib
import json
import os
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,default=ROOT/'.cache/mrl_glasses/kaggle/mrl-eye-dataset.zip')
    parser.add_argument('--per-class',type=int,default=256)
    args=parser.parse_args()
    import cv2
    import numpy as np
    from driver_monitor.eye_glasses import mrl_annotation,sample_mrl
    from driver_monitor.models import Classifier,prepare_rgb,sha256
    from driver_monitor.multiview_learning import evaluate
    out=ROOT/'reports/eye_glasses_20261013'
    data_dir=ROOT/'data_collection/eye_glasses/mrl_audit'
    out.mkdir(parents=True,exist_ok=True);data_dir.mkdir(parents=True,exist_ok=True)
    known_raw,known_input=set(),set()
    for path in (ROOT/'.cache/eye_refinement_v4/records.json',ROOT/'kaggle_upload/multiview_20261013/dataset.json'):
        if path.exists():
            for row in json.loads(path.read_text(encoding='utf-8'))['records']:
                if row.get('task','eye')=='eye':
                    known_raw.add(row['sha256']);known_input.add(row['input_sha256'])
    checkpoints={'original':ROOT/'models/manifest.json',
                 'current_eye_v4':ROOT/'models/yawn_kaggle_near_medium/manifest.json',
                 'multiview_candidate':ROOT/'models/multiview_20261013/manifest.json'}
    current=Classifier(checkpoints['current_eye_v4'],'eye','onnx')
    with zipfile.ZipFile(args.archive) as archive:
        catalog=[a for member in archive.namelist() if (a:=mrl_annotation(member)) is not None]
        test=[r for r in catalog if r['source_split']=='test']
        assert test,'No labeled MRL test images'
        # The supplied Kaggle test partition contains no glasses+Closed images.
        # Audit all metadata strata explicitly; this is NOT an independent test.
        selected=sample_mrl(catalog,args.per_class*4)
        decoded={};eligible=[];overlap=[]
        for index,row in enumerate(selected):
            raw=archive.read(row['member'])
            image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            assert image is not None,row['member']
            raw_hash=hashlib.sha256(raw).hexdigest()
            pixel_hash=hashlib.sha256(prepare_rgb(image,current.spec).tobytes()).hexdigest()
            if raw_hash in known_raw or pixel_hash in known_input:
                overlap.append(row['member']);continue
            decoded[row['member']]=(raw,image)
            eligible.append({**row,'sha256':raw_hash,'input_sha256':pixel_hash})
        selected=sample_mrl(eligible,args.per_class)
        images=[];rows=[]
        for index,row in enumerate(selected):
            raw,image=decoded[row['member']]
            domain='glasses' if row['glasses'] else 'no_glasses'
            target=data_dir/f'{index:04d}_{Path(row["member"]).name}'
            target.write_bytes(raw)
            rows.append({**row,'file':target.relative_to(ROOT).as_posix(),
                         'domain':domain,'source':domain,
                         'resolution':'IR_native_crop','quality':'usable',
                         'image_width':image.shape[1],'image_height':image.shape[0]})
            images.append(image)
    current.close()
    counts=Counter((r['glasses'],r['label']) for r in rows)
    assert all(counts[g,c]>0 for g in (False,True) for c in ('Closed','Open'))
    audit={'source':'https://www.kaggle.com/datasets/tauilabdelilah/mrl-eye-dataset',
           'primary_source':'https://mrl.cs.vsb.cz/eyedataset.html','archive_sha256':sha256(args.archive),
           'catalog_images':len(catalog),'test_catalog_images':len(test),'sampled_images':len(rows),
           'catalog_counts':{f'{s}/{g}/{c}':n for (s,g,c),n in Counter((r['source_split'],r['glasses'],r['label']) for r in catalog).items()},
           'counts':{f'{g}/{c}':n for (g,c),n in counts.items()},'exact_known_overlap_excluded':overlap,
           'sampling':f'up to {args.per_class} per glasses/class from all source partitions; metadata-only round robin across subject/reflection/light/sensor',
           'test_partition_incomplete':'Supplied Kaggle test contains glasses/Open but zero glasses/Closed. All-source audit supplements the missing class and is not a heldout test.',
           'evaluation_scope':'balanced IR single-eye crop development audit, not live RGB, temporal blink or independent generalization',
           'subject_independence':False,'original_checkpoint_training_membership':'unknown; original Kaggle data may include MRL',
           'glasses_type':'MRL binary annotation only; does not encode prescription or transparent/sunglasses subtype',
           'image_quality_gate_tested':False,'rows':rows}
    (data_dir/'dataset.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    report={k:v for k,v in audit.items() if k!='rows'};report['models']={}
    predictions=[]
    for name,path in checkpoints.items():
        model=Classifier(path,'eye','onnx')
        probabilities=[]
        for index,(row,image) in enumerate(zip(rows,images)):
            p=model.predict(image);probabilities.append([p['Closed'],p['Open']])
            predictions.append({'model':name,**{k:row[k] for k in ('file','subject','glasses','label','reflection','lighting','sensor')},
                                'p_closed':p['Closed'],'p_open':p['Open'],
                                'argmax':max(p,key=p.get),'confidence_decision':max(p,key=p.get) if max(p.values())>=.8 else 'UNKNOWN'})
        values=np.asarray(probabilities)
        metrics=evaluate(rows,values,'eye')
        groups={}
        for attribute in ('glasses','reflection','lighting','sensor','subject'):
            for value in sorted({row[attribute] for row in rows},key=str):
                indexes=[i for i,r in enumerate(rows) if r[attribute]==value]
                groups[f'{attribute}={value}']=evaluate([rows[i] for i in indexes],values[indexes],'eye')
        report['models'][name]={'manifest':path.relative_to(ROOT).as_posix(),
                                'onnx_sha256':model.spec['artifacts']['onnx']['sha256'],
                                'metrics':metrics,'by_condition':groups}
        model.close()
        print(json.dumps({'model':name,'n':len(rows),'glasses':groups['glasses=True']['accuracy'],
                          'no_glasses':groups['glasses=False']['accuracy']},ensure_ascii=False),flush=True)
    report['temporal_recognition_measured']=False
    (out/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (out/'predictions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(predictions[0]));writer.writeheader();writer.writerows(predictions)
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(10,8))
    for i,(glass,title) in enumerate(((False,'Không kính'),(True,'Đeo kính'))):
        measured=report['models']['current_eye_v4']['by_condition'][f'glasses={glass}']
        for j,(metric,caption) in enumerate(((measured,'Argmax'),(measured['confidence_and_quality_gate'],'Confidence ≥0,8'))):
            matrix=np.asarray(metric['confusion_matrix'] if j==0 else metric['confusion_matrix_with_unknown'])
            ax=axes[i,j];ax.imshow(matrix,cmap='Blues',vmin=0,vmax=max(1,metric['samples']/2))
            ax.set_xticks(range(matrix.shape[1]),['Nhắm','Mở']+(['UNKNOWN'] if j else []));ax.set_yticks(range(2),['Nhắm','Mở'])
            ax.set_title(title+' · '+caption);ax.set_xlabel('Nhãn dự đoán');ax.set_ylabel('Nhãn thực tế')
            for (r,c),n in np.ndenumerate(matrix):ax.text(c,r,str(n),ha='center',va='center',fontsize=15,color='white' if n>metric['samples']*.3 else '#162b32')
    fig.suptitle('Model mắt hiện tại · MRL audit · Crop mắt hồng ngoại',fontsize=15)
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(out/'current_confusion_matrix.png',dpi=165);plt.close(fig)
    # Review source labels/visibility independently of the model in a contact sheet.
    from PIL import Image,ImageDraw
    chosen=[]
    for glasses in (False,True):
        for label in ('Closed','Open'):
            chosen.extend([i for i,r in enumerate(rows) if r['glasses']==glasses and r['label']==label][:6])
    sheet=Image.new('RGB',(6*180,4*165),'#ffffff');draw=ImageDraw.Draw(sheet)
    for slot,index in enumerate(chosen):
        row=rows[index];image=Image.fromarray(cv2.cvtColor(images[index],cv2.COLOR_BGR2RGB));image.thumbnail((168,123))
        x=(slot%6)*180+6;y=(slot//6)*165+27
        sheet.paste(image,(x,y));draw.text((x,y-20),f'{row["subject"]} {row["label"]} G:{int(row["glasses"])}',fill='black')
    sheet.save(ROOT/'.cache/mrl_glasses/sample_review.png')
    print('Saved',out/'evaluation.json',flush=True)


if __name__=='__main__':main()
