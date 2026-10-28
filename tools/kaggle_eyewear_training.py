"""Train an independent RGB eyewear selector on Kaggle GPU. Never trains eye/yawn."""
import argparse
import csv
import json
import random
import sys
import time
import zipfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True)
    p.add_argument('--epochs',type=int,default=10);args=p.parse_args()
    root=Path(args.root);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(root/'support'))
    import cv2
    import numpy as np
    import torch
    from torchvision.models import mobilenet_v3_small,MobileNet_V3_Small_Weights
    from torch.utils.data import DataLoader,Dataset
    from driver_monitor.config import Config
    from driver_monitor.models import prepare_rgb,prepare_tensor,sha256
    from driver_monitor.vision import Vision
    from driver_monitor.multiview_learning import augment_native
    assert torch.cuda.is_available(),'GPU required; CPU training disabled'
    torch.set_num_threads(2);torch.manual_seed(42);np.random.seed(42);random.seed(42)
    dataset=next(Path('/kaggle/input').rglob('list_attr_celeba.csv')).parent
    partitions={r['image_id']:int(r['partition']) for r in csv.DictReader((dataset/'list_eval_partition.csv').open())}
    attributes=list(csv.DictReader((dataset/'list_attr_celeba.csv').open()))
    image_root=next(Path('/kaggle/input').rglob('000001.jpg')).parent
    options=json.loads((root/'crop_config.json').read_text());options.pop('manifest',None);options.pop('log_dir',None)
    monitor=options.pop('monitor',None)
    config=Config(manifest=root/'runtime_manifest.json',**options)
    vision=Vision(config)
    spec={'classes':['no_glasses','glasses'],'input_size':128,'output':'probabilities',
          'preprocessing':{'color':'RGB','resize':'shorter_center_crop','resize_shorter':128,
                           'interpolation':'bilinear','mean':[.485,.456,.406],'std':[.229,.224,.225]}}
    cache=[];rng=random.Random(42);counts={};rejected={};hash_owner={}
    began=time.monotonic()
    for split,partition,limits in [('train',0,(5000,5000)),('val',1,(2000,600)),('test',2,(2000,600))]:
        for label,limit in enumerate(limits):
            pool=[r for r in attributes if partitions[r['image_id']]==partition and int(r['Eyeglasses'])==(1 if label else -1)]
            rng.shuffle(pool);accepted=0;reject=0
            for row in pool:
                image=cv2.imread(str(image_root/row['image_id']))
                if image is None:reject+=1;continue
                result=vision.observe(image)
                if result.quality!='usable' or result.crops is None:reject+=1;continue
                crop=result.crops[2];rgb=prepare_rgb(crop,spec)
                import hashlib
                key=hashlib.sha256(rgb.tobytes()).hexdigest()
                if key in hash_owner:reject+=1;continue
                hash_owner[key]=(split,label)
                # RAM only. Do not redistribute CelebA pixels in output or private uploads.
                cache.append({'id':row['image_id'],'split':split,'label':label,'crop':crop,
                              'input_sha256':key,'quality':result.metrics})
                accepted+=1
                if accepted>=limit:break
            counts[f'{split}/{spec["classes"][label]}']=accepted;rejected[f'{split}/{label}']=reject
            print('Crops',split,label,accepted,'rejected',reject,flush=True)
    train=[r for r in cache if r['split']=='train'];val=[r for r in cache if r['split']=='val'];test=[r for r in cache if r['split']=='test']
    assert min(counts.values())>=300,'Insufficient data per partition/class'
    class Images(Dataset):
        def __init__(self,rows,training=False):self.rows=rows;self.training=training;self.rng=np.random.default_rng(42)
        def __len__(self):return len(self.rows)
        def __getitem__(self,i):
            r=self.rows[i];crop=augment_native(r['crop'],self.rng) if self.training else r['crop']
            if self.training and self.rng.random()<.5:crop=np.ascontiguousarray(crop[:,::-1])
            return torch.from_numpy(prepare_tensor(prepare_rgb(crop,spec),spec)[0]),r['label']
    def probabilities(model,rows):
        result=[];model.eval()
        with torch.inference_mode():
            for x,_ in DataLoader(Images(rows),batch_size=128,shuffle=False,num_workers=0):
                result.extend(torch.softmax(model(x.cuda()),1).cpu().numpy())
        return np.asarray(result)
    def metrics(rows,scores,threshold):
        truth=np.asarray([r['label'] for r in rows]);pred=scores[:,1]>=threshold
        matrix=np.zeros((2,2),int)
        for actual,predicted in zip(truth,pred):matrix[actual,int(predicted)]+=1
        tn,fp,fn,tp=matrix.ravel();precision=float(tp/max(tp+fp,1));recall=float(tp/max(tp+fn,1))
        f1=[]
        for i in (0,1):f1.append(float(2*matrix[i,i]/max(matrix[i,:].sum()+matrix[:,i].sum(),1)))
        return {'count':len(rows),'confusion_matrix':matrix.tolist(),'accuracy':float((tn+tp)/len(rows)),
                'macro_f1':sum(f1)/2,'glasses_precision':precision,'glasses_recall':recall,
                'no_glasses_false_route_rate':float(fp/max(tn+fp,1)),'threshold':float(threshold)}
    def threshold_for(rows,scores):
        choices=[]
        for threshold in sorted(set([.8,.85,.9,.95,.97,.98,.99,.995,.999]+[float(v) for v in scores[:,1] if .8<=v<1])):
            metric=metrics(rows,scores,threshold)
            if metric['glasses_precision']>=.995 and metric['no_glasses_false_route_rate']<=.002 and metric['glasses_recall']>=.3:
                choices.append(metric)
        return max(choices,key=lambda m:(m['glasses_recall'],-m['no_glasses_false_route_rate'],-m['threshold'])) if choices else None
    model=mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    model.classifier[3]=torch.nn.Linear(model.classifier[3].in_features,2);model.cuda()
    optimizer=torch.optim.AdamW(model.parameters(),lr=2e-4,weight_decay=1e-4)
    scaler=torch.amp.GradScaler('cuda');history=[];best=None;best_state=None;selected=None
    loader=DataLoader(Images(train,True),batch_size=128,shuffle=True,num_workers=0)
    for epoch in range(1,args.epochs+1):
        model.train();losses=[]
        for x,y in loader:
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.float16):loss=torch.nn.functional.cross_entropy(model(x.cuda()),y.cuda())
            scaler.scale(loss).backward();scaler.unscale_(optimizer);torch.nn.utils.clip_grad_norm_(model.parameters(),1)
            scaler.step(optimizer);scaler.update();losses.append(float(loss))
        scores=probabilities(model,val);gate=threshold_for(val,scores);raw=metrics(val,scores,.5)
        item={'epoch':epoch,'train_loss':sum(losses)/len(losses),'validation_raw':raw,'validation_gate':gate}
        history.append(item);print(json.dumps(item),flush=True)
        if gate is not None:
            score=(gate['glasses_recall'],raw['macro_f1'])
            if best is None or score>best:
                best=score;selected=epoch;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    report={'status':'no_qualified_gate','source':'jessicali9530/celeba-dataset','source_primary':'https://mmlab.ie.cuhk.edu.hk/projects/CelebA.html',
            'counts':counts,'rejected':rejected,'split':'provided CelebA partition; identity metadata not independently audited',
            'history':history,'selected_epoch':selected,'spec':spec,'gpu':torch.cuda.get_device_name(0),
            'limits':['Celebrity still photos; no USB RGB glasses video yet','Eyeglasses attribute does not certify clear prescription lens subtype',
                      'Validation-selected precision target is not a guarantee on another camera'],
            'seconds':time.monotonic()-began,'base_models_modified':False}
    if best_state is not None:
        model.load_state_dict(best_state);model.eval();threshold=history[selected-1]['validation_gate']['threshold']
        scores=probabilities(model,test)
        report.update(status='experimental_gate',test_raw=metrics(test,scores,.5),test_gate=metrics(test,scores,threshold),
                      threshold=threshold,validation=history[selected-1])
        torch.save({'architecture':'torchvision_mobilenet_v3_small','state_dict':best_state,'spec':spec},out/'eyewear.pt')
        class Probabilities(torch.nn.Module):
            def __init__(self,net):super().__init__();self.net=net
            def forward(self,x):return torch.softmax(self.net(x),dim=1)
        wrapped=Probabilities(model.cpu()).eval()
        torch.onnx.export(wrapped,torch.zeros(1,3,128,128),str(out/'eyewear.onnx'),opset_version=17,
                          input_names=['images'],output_names=['probabilities'],dynamo=False)
        spec.update(architecture='MobileNetV3-Small',artifact={'file':'eyewear.onnx','sha256':sha256(out/'eyewear.onnx')})
        manifest={'schema_version':1,'kind':'driver_monitor_eyewear_selector','classifier':spec,
                  'gate':{'enter_probability':threshold,'confirm_seconds':1.5,'poll_seconds':.5,'max_score_age_seconds':.8},
                  'status':'experimental; real RGB glasses camera acceptance pending'}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
        with (out/'test_predictions.csv').open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['image_id','actual','p_glasses','prediction_raw','prediction_gate','input_sha256'])
            for r,s in zip(test,scores):writer.writerow([r['id'],spec['classes'][r['label']],float(s[1]),int(s[1]>=.5),int(s[1]>=threshold),r['input_sha256']])
        samples=test[:16]+[r for r in test if r['label']==1][:16]
        np.savez_compressed(out/'parity_inputs.npz',inputs=np.concatenate([prepare_tensor(prepare_rgb(r['crop'],spec),spec) for r in samples]),
                            probabilities=probabilities(model.cuda(),samples))
    (out/'evaluation.json').write_text(json.dumps(report,indent=2))
    with zipfile.ZipFile(out.parent/'eyewear_result.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for file in out.iterdir():archive.write(file,file.name)
    print('Done:',report['status'],flush=True)


if __name__=='__main__':main()
