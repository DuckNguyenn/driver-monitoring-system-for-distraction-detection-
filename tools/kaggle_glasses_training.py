"""GPU-only eye adaptation: last C2f and Classify, guarded RGB rehearsal."""
from pathlib import Path
from collections import Counter
import argparse
import copy
import hashlib
import json
import sys
import zipfile
import cv2
import numpy as np


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1<<20),b''):value.update(chunk)
    return value.hexdigest()


def logits(model,x):
    for block in list(model.model)[:-1]:x=block(x)
    head=model.model[-1]
    return head.linear(head.pool(head.conv(x)).flatten(1))


def predict(model,rows,root,spec,device):
    import torch
    from driver_monitor.models import prepare_rgb,prepare_tensor
    result=[]
    with torch.inference_mode():
        for start in range(0,len(rows),64):
            tensor=np.concatenate([prepare_tensor(prepare_rgb(cv2.imread(str(root/r['file'])),spec),spec) for r in rows[start:start+64]])
            result.extend(torch.softmax(logits(model,torch.from_numpy(tensor).to(device)),1).float().cpu().numpy())
    return np.asarray(result,dtype=np.float32)


def metrics(rows,p):
    from driver_monitor.multiview_learning import evaluate
    from driver_monitor.glasses_training import group_name
    result={}
    names=['rgb_rehearsal','mrl_glasses','mrl_no_glasses']
    if any(r.get('new_glasses_camera') for r in rows):names.append('rgb_glasses')
    for name in names:
        indexes=[i for i,r in enumerate(rows) if group_name(r)==name]
        result[name]=evaluate([rows[i] for i in indexes],p[indexes],'eye')
    return result


def plot_matrix(metric,path,title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(9,4))
    for ax,(matrix,columns,caption) in zip(axes,[(metric['confusion_matrix'],['Closed','Open'],'argmax'),
           (metric['confidence_and_quality_gate']['confusion_matrix_with_unknown'],['Closed','Open','UNKNOWN'],'confidence 0.8')]):
        values=np.asarray(matrix);ax.imshow(values,cmap='Blues')
        ax.set_xticks(range(len(columns)),columns);ax.set_yticks(range(2),['Closed','Open'])
        ax.set_xlabel('Predicted');ax.set_ylabel('Actual');ax.set_title(caption)
        for (i,j),n in np.ndenumerate(values):ax.text(j,i,str(n),ha='center',va='center',color='white' if n>values.max()/2 else 'black')
    fig.suptitle(title);fig.tight_layout();fig.savefig(path,dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--epochs',type=int,default=24);parser.add_argument('--patience',type=int,default=7)
    args=parser.parse_args()
    import torch
    from ultralytics import YOLO
    from torch.utils.data import Dataset,DataLoader,WeightedRandomSampler
    from importlib.metadata import version
    if not torch.cuda.is_available():raise RuntimeError('Kaggle GPU required; CPU training disabled')
    torch.set_num_threads(2);torch.manual_seed(42);np.random.seed(42);torch.cuda.manual_seed_all(42)
    root=Path(args.root).resolve();out=Path(args.output).resolve()
    if out.exists() and any(out.iterdir()):raise ValueError('Output already exists')
    out.mkdir(parents=True,exist_ok=True)
    bundle=json.loads((root/'bundle.json').read_text(encoding='utf-8'))
    assert bundle['kind']=='driver_monitor_glasses_adaptation'
    for file,expected in bundle['checksums'].items():
        path=(root/file).resolve()
        if not path.is_relative_to(root) or digest(path)!=expected:raise ValueError('Changed bundle file: '+file)
    sys.path.insert(0,str(root/'support'))
    from driver_monitor.models import prepare_rgb,prepare_tensor
    from driver_monitor.glasses_training import validate_subjects,validate_rgb_subjects,sampler_weights,augment_glasses,glasses_selection,sampling_mass
    data=json.loads((root/'dataset.json').read_text(encoding='utf-8'));rows=data['records'];spec=data['runtime_spec']
    validate_subjects(rows)
    if data.get('new_rgb_glasses_camera_present'):
        validate_rgb_subjects(rows,require_complete=True)
    seen={}
    for row in rows:
        key=row['input_sha256'];owner=(row['split'],row['label'])
        if key in seen and seen[key]!=owner:raise ValueError('Pixels crossed splits or label conflict')
        seen[key]=owner
        image=cv2.imread(str(root/row['file']))
        if image is None or hashlib.sha256(prepare_rgb(image,spec).tobytes()).hexdigest()!=key:raise ValueError('Crop/preprocessing changed')
    train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='val'];test=[r for r in rows if r['split']=='test']
    device=torch.device('cuda:0');loaded=YOLO(str(root/bundle['checkpoint']))
    assert loaded.task=='classify' and list(loaded.names.values())==['Closed','Open']
    model=loaded.model.float().eval().to(device)
    assert len(model.model)==10 and type(model.model[8]).__name__=='C2f' and type(model.model[9]).__name__=='Classify'
    for parameter in model.parameters():parameter.requires_grad=False
    for index in (8,9):
        for parameter in model.model[index].parameters():parameter.requires_grad=True
    frozen={k:v.detach().cpu().clone() for k,v in model.state_dict().items() if not k.startswith(('model.8.','model.9.')) or 'running_' in k or 'num_batches_tracked' in k}
    baseline_val=metrics(val,predict(model,val,root,spec,device))
    print(json.dumps({'GPU':torch.cuda.get_device_name(0),'torch':torch.__version__,'numpy':np.__version__,
                      'baseline_validation':{k:{'macro_f1':v['macro_f1'],'accuracy':v['accuracy']} for k,v in baseline_val.items()} }),flush=True)
    class Crops(Dataset):
        def __init__(self):self.rng=np.random.default_rng(42)
        def __len__(self):return len(train)
        def __getitem__(self,index):
            row=train[index];image=cv2.imread(str(root/row['file']))
            image=augment_glasses(image,self.rng,True)
            return torch.from_numpy(prepare_tensor(prepare_rgb(image,spec),spec)[0]),data['classes'].index(row['label'])
    generator=torch.Generator().manual_seed(42)
    sampler=WeightedRandomSampler(sampler_weights(train),min(len(train),2048),replacement=True,generator=generator)
    loader=DataLoader(Crops(),sampler=sampler,batch_size=64,num_workers=0,pin_memory=True)
    optimizer=torch.optim.AdamW([{'params':model.model[8].parameters(),'lr':1e-5},
                                {'params':model.model[9].parameters(),'lr':5e-5}],weight_decay=1e-4)
    scaler=torch.amp.GradScaler('cuda');best=None;best_score=-float('inf');selected=None;stale=0;trials=[]
    for epoch in range(1,args.epochs+1):
        model.eval();loss_sum=sample_count=0
        for x,y in loader:
            x,y=x.to(device),y.to(device);optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.float16):loss=torch.nn.functional.cross_entropy(logits(model,x),y)
            if not torch.isfinite(loss):raise RuntimeError('Non-finite loss')
            scaler.scale(loss).backward();scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.)
            scaler.step(optimizer);scaler.update();loss_sum+=float(loss.detach())*len(y);sample_count+=len(y)
        measured=metrics(val,predict(model,val,root,spec,device));score,reasons=glasses_selection(measured,baseline_val)
        trial={'epoch':epoch,'loss':loss_sum/sample_count,'score':score,'rejections':reasons,
               'validation':{k:{'macro_f1':v['macro_f1'],'accuracy':v['accuracy']} for k,v in measured.items()}}
        trials.append(trial);print(json.dumps(trial),flush=True)
        if not reasons and score>best_score:
            best={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};best_score=score;selected=epoch;stale=0
        else:stale+=1
        if best is not None and stale>=args.patience:break
    meta={'status':'no_qualified_candidate' if best is None else 'experimental_glasses_candidate',
          'GPU':torch.cuda.get_device_name(0),'versions':{k:version(k) for k in ('torch','torchvision','ultralytics','numpy','onnx','onnxruntime')},
          'selected_epoch':selected,'trials':trials,'baseline_validation':baseline_val,
          'new_rgb_glasses_camera_present':bool(data.get('new_rgb_glasses_camera_present')),'live_camera_acceptance':False,'event_accuracy':None,
          'test_used_for_selection':False,'mrl_subject_split':data['mrl_subject_split'],
          'mrl_pretraining_membership':'unknown; independence from original checkpoint is unproven',
          'prior_audit_seen':True,'sampling_mass':sampling_mass(train),
          'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),
          'trained_layers':[8,9],'thresholds_changed':False,'promotion_status':'not_promoted'}
    if best is not None:
        model.load_state_dict(best);model.cpu().float().eval()
        assert all(torch.equal(model.state_dict()[k],v) for k,v in frozen.items())
        loaded.ckpt.update(train_metrics={},train_results={},epoch=selected);loaded.save(out/'best_eye.pt')
        serialized=YOLO(str(out/'best_eye.pt')).model.float().eval()
        candidate_gpu=copy.deepcopy(serialized).to(device)
        serialized_val=metrics(val,predict(candidate_gpu,val,root,spec,device))
        _,reasons=glasses_selection(serialized_val,baseline_val)
        if reasons:raise RuntimeError('Serialized checkpoint failed validation: '+repr(reasons))
        meta['candidate_validation']=serialized_val;meta['frozen_backbone_and_bn_buffers_unchanged']=True
        original=YOLO(str(root/bundle['checkpoint'])).model.float().eval().to(device)
        # Stage test is used once after checkpoint selection; source RGB regression is labeled separately.
        a=predict(original,test,root,spec,device);b=predict(candidate_gpu,test,root,spec,device)
        meta['test']={'baseline':metrics(test,a),'candidate':metrics(test,b)}
        meta['test_predictions']=[{**{k:r.get(k) for k in ('file','domain','subject','source','resolution','glasses','reflection','lighting','label')},
                                  'baseline':x.tolist(),'candidate':y.tolist()} for r,x,y in zip(test,a,b)]
        for version_name in ('baseline','candidate'):
            for group,metric in meta['test'][version_name].items():plot_matrix(metric,out/f'{version_name}_{group}_matrix.png',version_name+' '+group+' stage test')
        import onnx
        import onnxruntime as ort
        serialized.model[-1].export=True
        torch.onnx.export(serialized,torch.zeros(1,3,224,224),str(out/'best_eye.onnx'),input_names=['images'],
                          output_names=['probabilities'],opset_version=12,dynamo=False)
        serialized.model[-1].export=False
        graph=onnx.load(out/'best_eye.onnx');onnx.checker.check_model(graph)
        assert graph.ir_version<=10
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        session=ort.InferenceSession(str(out/'best_eye.onnx'),options,providers=['CPUExecutionProvider'])
        deltas=[]
        with torch.inference_mode():
            for row in test[::max(1,len(test)//32)][:32]:
                x=prepare_tensor(prepare_rgb(cv2.imread(str(root/row['file'])),spec),spec)
                a=torch.softmax(logits(serialized,torch.from_numpy(x)),1).numpy()
                b=session.run(None,{'images':x})[0];deltas.append(float(np.max(np.abs(a-b))))
        assert max(deltas)<=1e-4
        meta['parity']={'samples':len(deltas),'max_probability_delta':max(deltas),'passed':True,'onnx_ir':graph.ir_version}
        manifest=json.loads((root/'base_manifest.json').read_text(encoding='utf-8'))
        manifest['classifiers']['eye']['artifacts']={backend:{'file':file,'sha256':digest(out/file)} for backend,file in (('torch','best_eye.pt'),('onnx','best_eye.onnx'))}
        manifest['starting_model_refinement']=manifest.pop('refinement',{})
        manifest['starting_model_export_versions']=manifest.pop('export_versions',{})
        manifest['export_versions']=meta['versions'];manifest['deployment_validation']='Glasses adaptation candidate; RGB video event accuracy and Radxa acceptance pending'
        manifest['glasses_adaptation']={'dataset_sha256':digest(root/'dataset.json'),'starting_pt_sha256':digest(root/bundle['checkpoint']),
                                      'selected_epoch':selected,'layers':[8,9],'stage_subject_split':data['mrl_subject_split'],
                                      'test_used_for_selection':False,'new_rgb_glasses_camera_present':meta['new_rgb_glasses_camera_present'],'promotion_status':'not_promoted'}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        import yaml
        settings=json.loads((root/'runtime_settings.json').read_text(encoding='utf-8'))
        settings.update(manifest='manifest.json',backend='onnx',log_dir='../../logs')
        (out/'runtime.yaml').write_text(yaml.safe_dump(settings,sort_keys=False),encoding='utf-8')
    (out/'evaluation.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    archive=out.parent/'glasses_result.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        for file in out.glob('*'):
            if file.is_file():zipped.write(file,file.name)
    print(json.dumps({'result':str(archive),'sha256':digest(archive),'bytes':archive.stat().st_size,'status':meta['status']}),flush=True)


if __name__=='__main__':main()
