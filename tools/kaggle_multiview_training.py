"""Cold-process Kaggle GPU fine-tuning of eye/yawn Classify blocks."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import sys
import zipfile
from collections import Counter

import cv2
import numpy as np


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1<<20),b''):h.update(part)
    return h.hexdigest()


def load(root):
    bundle=json.loads((root/'bundle.json').read_text(encoding='utf-8'))
    if bundle.get('kind')!='driver_monitor_multiview':raise ValueError('Wrong bundle type')
    for name,expected in bundle['checksums'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or digest(path)!=expected:raise ValueError('Changed bundle file: '+name)
    sys.path.insert(0,str(root/'support'))
    data=json.loads((root/'dataset.json').read_text(encoding='utf-8'))
    from driver_monitor.models import prepare_rgb
    assignments={}
    for row in data['records']:
        key=(row['task'],row['input_sha256'])
        if key in assignments and assignments[key]!=(row['split'],row['label']):raise ValueError('Duplicate pixels across splits or labels')
        assignments[key]=(row['split'],row['label'])
        image=cv2.imread(str(root/row['file']))
        if image is None or hashlib.sha256(prepare_rgb(image,data['runtime_specs'][row['task']]).tobytes()).hexdigest()!=row['input_sha256']:
            raise ValueError('Preprocessing mismatch')
        if row['source']==data['test_clip'] and row['split']!='test':raise ValueError('Test clip leaked into training')
    if not data.get('subject_independence') is False:raise ValueError('This dataset does not establish subject independence')
    return bundle,data


def logits(model,x):
    for layer in list(model.model)[:-1]:x=layer(x)
    head=model.model[-1]
    return head.linear(head.pool(head.conv(x)).flatten(1))


def probabilities(model,rows,root,spec,device,batch=64):
    import torch
    from driver_monitor.models import prepare_rgb,prepare_tensor
    result=[]
    with torch.inference_mode():
        for start in range(0,len(rows),batch):
            x=np.concatenate([prepare_tensor(prepare_rgb(cv2.imread(str(root/r['file'])),spec),spec) for r in rows[start:start+batch]])
            result.extend(torch.softmax(logits(model,torch.from_numpy(x).to(device)),1).float().cpu().numpy())
    return np.asarray(result,dtype=np.float32)


def draw_matrices(metrics,name,path,title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matrices=[(metrics['confusion_matrix'],metrics['classes'],'Classifier argmax'),
              (metrics['confidence_and_quality_gate']['confusion_matrix_with_unknown'],metrics['classes']+['UNKNOWN'],'Confidence and image quality')]
    fig,axes=plt.subplots(1,2,figsize=(10,4.5))
    for ax,(values,columns,label) in zip(axes,matrices):
        values=np.array(values);ax.imshow(values,cmap='Blues')
        ax.set_xticks(range(len(columns)),columns);ax.set_yticks(range(2),metrics['classes'])
        ax.set_xlabel('Predicted');ax.set_ylabel('Actual');ax.set_title(label)
        for (i,j),value in np.ndenumerate(values):ax.text(j,i,str(value),ha='center',va='center',color='white' if value>values.max()/2 else 'black')
    fig.suptitle(title+' · '+name)
    fig.tight_layout();fig.savefig(path,dpi=170);plt.close(fig)


def train_one(name,root,output,bundle,data,args):
    import torch
    from ultralytics import YOLO
    from torch.utils.data import Dataset,DataLoader,WeightedRandomSampler
    from driver_monitor.models import prepare_rgb,prepare_tensor
    from driver_monitor.multiview_learning import CLASSES,augment_native,evaluate,validation_score
    rows=[r for r in data['records'] if r['task']==name]
    train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='val']
    test=[r for r in rows if r['split']=='test'];camera_train=[r for r in train if r['source'] in ('WIN_20261013_17_05_46_Pro','WIN_20261013_17_07_34_Pro')]
    if not train or not val or not test or any(not any(r['label']==label for r in val) for label in CLASSES[name]):raise ValueError('Insufficient train/val/test class support')
    if any(r['domain']!='static' for r in val):raise ValueError('Selection requires retained static validation only')
    device=torch.device('cuda:0');spec=data['runtime_specs'][name]
    loaded=YOLO(str(root/bundle['checkpoints'][name]))
    if list(loaded.names.values())!=CLASSES[name]:raise ValueError('Class order differs from manifest')
    model=loaded.model.float().eval().to(device);head=model.model[-1]
    for parameter in model.parameters():parameter.requires_grad=False
    for parameter in head.parameters():parameter.requires_grad=True
    prefix=f'model.{len(model.model)-1}.'
    frozen={k:v.detach().cpu().clone() for k,v in model.state_dict().items() if not k.startswith(prefix) or 'running_' in k or 'num_batches_tracked' in k}
    baseline_p=probabilities(model,val,root,spec,device,args.batch_size)
    baseline=evaluate(val,baseline_p,name)
    class NativeDataset(Dataset):
        def __init__(self):self.rng=np.random.default_rng(args.seed)
        def __len__(self):return len(train)
        def __getitem__(self,index):
            row=train[index];crop=cv2.imread(str(root/row['file']))
            crop=augment_native(crop,self.rng,True)
            rgb=prepare_rgb(crop,spec)
            return torch.from_numpy(prepare_tensor(rgb,spec)[0]),CLASSES[name].index(row['label'])
    groups=Counter((r['domain'],r['label']) for r in train)
    weights=[(.6 if r['domain']=='camera' else .4)/(2*groups[r['domain'],r['label']]) for r in train]
    generator=torch.Generator().manual_seed(args.seed)
    sampler=WeightedRandomSampler(weights,min(len(train),1536),replacement=True,generator=generator)
    loader=DataLoader(NativeDataset(),sampler=sampler,batch_size=args.batch_size,num_workers=0,pin_memory=True)
    optimizer=torch.optim.AdamW(head.parameters(),lr=args.learning_rate,weight_decay=1e-4)
    scaler=torch.amp.GradScaler('cuda')
    best_score,best_state,best_epoch=-float('inf'),None,None;stale=0;trials=[]
    for epoch in range(1,args.epochs+1):
        model.eval();loss_total=samples=0
        for x,y in loader:
            x,y=x.to(device),y.to(device);optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.float16):loss=torch.nn.functional.cross_entropy(logits(model,x),y)
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss')
            scaler.scale(loss).backward();scaler.step(optimizer);scaler.update()
            loss_total+=float(loss.detach())*len(y);samples+=len(y)
        measured=evaluate(val,probabilities(model,val,root,spec,device,args.batch_size),name)
        score,reasons=validation_score(measured,baseline)
        trial={'epoch':epoch,'loss':loss_total/samples,'score':score,'rejection_reasons':reasons}
        trials.append(trial);print(json.dumps({'task':name,**trial}),flush=True)
        if not reasons and score>best_score:
            best_score=score;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};best_epoch=epoch;stale=0
        else:stale+=1
        if best_state is not None and stale>=args.patience:break
    if best_state is None:raise RuntimeError('No candidate passed retained static validation for '+name)
    model.load_state_dict(best_state);model.cpu().float().eval()
    unchanged=all(torch.equal(model.state_dict()[k],value) for k,value in frozen.items())
    if not unchanged:raise RuntimeError('Frozen backbone/BN buffers changed')
    loaded.ckpt.update(train_metrics={},train_results={},epoch=best_epoch)
    loaded.save(output/f'best_{name}.pt')
    serialized=YOLO(str(output/f'best_{name}.pt')).model.cpu().float().eval()
    serialized_gpu=copy.deepcopy(serialized).to(device)
    serialized_val=evaluate(val,probabilities(serialized_gpu,val,root,spec,device,args.batch_size),name)
    _,serialized_reasons=validation_score(serialized_val,baseline)
    if serialized_reasons:raise RuntimeError('Serialized candidate failed retained validation')
    # Test is evaluated once, only after checkpoint selection and serialization.
    candidate_test_p=probabilities(serialized_gpu,test,root,spec,device,args.batch_size)
    original=YOLO(str(root/bundle['checkpoints'][name])).model.float().eval().to(device)
    baseline_test_p=probabilities(original,test,root,spec,device,args.batch_size)
    candidate_train_p=probabilities(serialized_gpu,camera_train,root,spec,device,args.batch_size)
    baseline_train_p=probabilities(original,camera_train,root,spec,device,args.batch_size)
    camera_test={'baseline':evaluate(test,baseline_test_p,name),'candidate':evaluate(test,candidate_test_p,name)}
    training_diagnostic={'baseline':evaluate(camera_train,baseline_train_p,name),'candidate':evaluate(camera_train,candidate_train_p,name),
                         'note':'Training fit, not an independent evaluation.'}
    predictions=[]
    for row,a,b in zip(test,baseline_test_p,candidate_test_p):
        predictions.append({**{k:row.get(k) for k in ('source','frame','timestamp','resolution','eye_index','quality','label')},
                            'baseline':a.tolist(),'candidate':b.tolist()})
    report={'task':name,'classes':CLASSES[name],'selected_epoch':best_epoch,'trials':trials,
            'trainable_parameters':sum(p.numel() for p in head.parameters()),
            'backbone_and_bn_buffers_unchanged':unchanged,'baseline_validation':baseline,
            'candidate_validation':serialized_val,'heldout_camera':camera_test,
            'camera_train_diagnostic':training_diagnostic,'heldout_predictions':predictions,
            'selection_split':'val','selection_domain':'retained_static_only','test_used_for_selection':False,
            'subject_independence':False,'event_accuracy':None,'camera_live_acceptance':False}
    (output/f'{name}_evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for version,metric in camera_test.items():
        for group,value in metric['groups'].items():
            resolution=group.rsplit('/',1)[1]
            draw_matrices(value,name,output/f'{name}_{version}_{resolution}_matrix.png',version+' held-out clip · '+resolution)
    import onnx
    import onnxruntime as ort
    serialized.model[-1].export=True
    torch.onnx.export(serialized,torch.zeros(1,3,224,224),str(output/f'best_{name}.onnx'),
                      input_names=['images'],output_names=['probabilities'],opset_version=12,dynamo=False)
    graph=onnx.load(output/f'best_{name}.onnx');onnx.checker.check_model(graph)
    if graph.ir_version>10:raise RuntimeError('ONNX IR unsupported by existing PC runtime')
    serialized.model[-1].export=False
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(output/f'best_{name}.onnx'),options,providers=['CPUExecutionProvider'])
    differences=[]
    with torch.inference_mode():
        for row in test[::max(1,len(test)//32)][:32]:
            x=prepare_tensor(prepare_rgb(cv2.imread(str(root/row['file'])),spec),spec)
            a=torch.softmax(logits(serialized,torch.from_numpy(x)),1).numpy()
            b=session.run(None,{'images':x})[0]
            differences.append(float(np.max(np.abs(a-b))))
    parity={'samples':len(differences),'max_probability_delta':max(differences),'passed':max(differences)<=1e-4,
            'onnx_ir':graph.ir_version,'onnx_version':onnx.__version__,'onnxruntime_version':ort.__version__}
    if not parity['passed']:raise RuntimeError('PT/ONNX parity failed')
    (output/f'{name}_parity.json').write_text(json.dumps(parity,indent=2),encoding='utf-8')
    del original,serialized_gpu,model
    torch.cuda.empty_cache()
    return report,parity


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--epochs',type=int,default=30);parser.add_argument('--batch-size',type=int,default=64)
    parser.add_argument('--learning-rate',type=float,default=1e-4);parser.add_argument('--patience',type=int,default=7)
    parser.add_argument('--seed',type=int,default=42);args=parser.parse_args()
    import torch
    if not torch.cuda.is_available():raise RuntimeError('GPU required; CPU training is disabled')
    torch.set_num_threads(2);torch.manual_seed(args.seed);np.random.seed(args.seed);torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark=False
    root,output=Path(args.root).resolve(),Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):raise ValueError('Output exists')
    output.mkdir(parents=True,exist_ok=True)
    bundle,data=load(root)
    print(json.dumps({'GPU':torch.cuda.get_device_name(0),'torch':torch.__version__,'numpy':np.__version__,'python':sys.version}),flush=True)
    reports={};parities={}
    for name in ('eye','yawn'):reports[name],parities[name]=train_one(name,root,output,bundle,data,args)
    manifest=json.loads((root/'base_manifest.json').read_text(encoding='utf-8'))
    from importlib.metadata import version
    # Prior refinements describe the starting weights, not this run's artifacts.
    manifest['starting_model_refinement']=manifest.pop('refinement',{})
    manifest['starting_model_export_versions']=manifest.pop('export_versions',{})
    manifest['export_versions']={name:version(name) for name in ('torch','torchvision','ultralytics','onnx','onnxruntime','numpy')}
    for name in ('eye','yawn'):
        manifest['classifiers'][name]['artifacts']={backend:{'file':f'best_{name}.{ext}','sha256':digest(output/f'best_{name}.{ext}')}
                                                   for backend,ext in (('torch','pt'),('onnx','onnx'))}
    manifest['deployment_validation']='Experimental multiview candidate: same-person held-out clip; independent live camera/person/Radxa acceptance pending'
    manifest['multiview_refinement']={'dataset_sha256':digest(root/'dataset.json'),'training_clips':['WIN_20261013_17_05_46_Pro','WIN_20261013_17_07_34_Pro'],
                                    'test_clip':data['test_clip'],'selection_domain':'retained_static_validation_only',
                                    'test_used_for_selection':False,'subject_independence':False,
                                    'selected_epochs':{name:report['selected_epoch'] for name,report in reports.items()},
                                    'starting_checkpoint_sha256':{name:digest(root/file) for name,file in bundle['checkpoints'].items()},
                                    'method':'Classify conv/BN affine/Linear; frozen backbone and BN buffers',
                                    'augmentation_at_inference':False}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    import yaml
    settings=json.loads((root/'runtime_settings.json').read_text(encoding='utf-8'))
    settings.update(manifest='manifest.json',log_dir='../../logs',backend='onnx')
    (output/'runtime.yaml').write_text(yaml.safe_dump(settings,sort_keys=False),encoding='utf-8')
    summary={'status':'experimental_multiview','GPU':torch.cuda.get_device_name(0),'torch':torch.__version__,
             'numpy':np.__version__,'python':sys.version,'test_clip':data['test_clip'],'subject_independence':False,
             'selection_domain':'retained_static_validation_only','metrics':{name:{'epoch':report['selected_epoch'],
                       'heldout_camera':report['heldout_camera']} for name,report in reports.items()},'parity':parities}
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    archive=output.parent/'multiview_result.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in output.glob('*'):
            if path.is_file():z.write(path,path.name)
    print(json.dumps({'result':str(archive),'sha256':digest(archive),'bytes':archive.stat().st_size}),flush=True)


if __name__=='__main__':main()
