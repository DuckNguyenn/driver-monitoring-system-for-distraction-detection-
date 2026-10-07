"""Fine-tune YOLO's Classify block with a frozen backbone and reviewed eye crops.

The initial linear-only candidates did not meet the combined open-eye
regression and true-closure criteria. Cache backbone maps, then train the
existing 1x1 conv/BN affine parameters and final linear layer. BatchNorm running
statistics stay fixed. Architecture, preprocessing and class order stay fixed.
"""
import argparse
import copy
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / '.cache/ultralytics'))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
import torch
from ultralytics import YOLO
from driver_monitor.config import load_config
from driver_monitor.models import Classifier, artifact_path, prepare_rgb, prepare_tensor, read_manifest, sha256
from driver_monitor.exporting import export_models
from driver_monitor.vision import Vision
from refine_eye_head import augment, metrics, save, CLASSES, BASELINE, LABELS

CACHE = ROOT / '.cache/eye_refinement_v2'


def prepare():
    provenance = json.loads((CACHE / 'records.json').read_text())
    if provenance['labels_sha256'] != sha256(LABELS):
        raise ValueError('Reviewed eye labels changed')
    config = load_config(ROOT / 'configs/camera_pc.yaml', manifest=BASELINE)
    spec = read_manifest(BASELINE)['classifiers']['eye']
    model = Classifier(BASELINE, 'eye', 'torch').model
    records = provenance['records']
    maps = np.empty((len(records),256,7,7),np.float16)
    caught, pending = [], []
    hook = model.model[-1].conv.register_forward_pre_hook(
        lambda module, inputs: caught.append(inputs[0].detach().numpy().copy()))
    current_path, crops, image, variants = None, None, None, {}
    def flush(start):
        caught.clear()
        with torch.inference_mode():
            model(torch.from_numpy(np.concatenate(pending)))
        maps[start:start+len(pending)] = caught[0]
        pending.clear()
    start = 0
    for index, row in enumerate(records):
        if row['path'] != current_path:
            current_path = row['path']
            path = ROOT / current_path
            if sha256(path) != row['sha256']:
                raise ValueError(f'Image changed: {path}')
            image = cv2.imread(str(path))
            crops = Vision(config).observe(image).crops if row['source'] == 'roi' else None
            variants = {}
        key = row.get('eye_index',-1)
        if key not in variants:
            variants[key] = dict(augment(crops[key] if crops is not None else image))
        rgb = prepare_rgb(variants[key][row['variant']], spec)
        if hashlib.sha256(rgb.tobytes()).hexdigest() != row['input_sha256']:
            raise ValueError('Backbone input changed')
        pending.append(prepare_tensor(rgb,spec))
        if len(pending) == 16:
            flush(start)
            start = index + 1
        if index and index % 1000 == 0:
            print(f'Backbone maps: {index}/{len(records)}',flush=True)
    if pending:
        flush(start)
    hook.remove()
    np.savez_compressed(CACHE / 'spatial_features.npz', features=maps)
    save(CACHE / 'spatial_source.json',{'records_sha256':sha256(CACHE / 'records.json'),
        'features_sha256':sha256(CACHE / 'spatial_features.npz'), 'baseline_manifest_sha256':sha256(BASELINE),
        'shape':list(maps.shape),'storage':'float16; train/evaluate float32'})
    print(json.dumps({'shape':list(maps.shape)}),flush=True)


def logits(tail, x):
    return tail.linear(tail.pool(tail.conv(x)).flatten(1))


def probabilities(tail, maps):
    values = []
    with torch.inference_mode():
        for index in range(0,len(maps),64):
            values.append(torch.softmax(logits(tail,maps[index:index+64].float()),1).numpy())
    return np.concatenate(values)


def train(output, epochs):
    provenance = json.loads((CACHE / 'records.json').read_text())
    spatial = json.loads((CACHE / 'spatial_source.json').read_text())
    if (spatial['records_sha256'] != sha256(CACHE / 'records.json')
            or spatial['baseline_manifest_sha256'] != sha256(BASELINE)
            or spatial['features_sha256'] != sha256(CACHE / 'spatial_features.npz')
            or provenance['labels_sha256'] != sha256(LABELS)):
        raise ValueError('Stale backbone maps')
    priority = {'train':0,'val':1,'test':2}
    owners = {}
    for row in provenance['records']:
        for digest in (row['sha256'],row['input_sha256']):
            owners[digest] = max(owners.get(digest,-1),priority[row['split']])
    excluded = {r['path'] for r in provenance['records'] if any(priority[r['split']] < owners[d]
                for d in (r['sha256'],r['input_sha256']))}
    records = [r for r in provenance['records'] if r['path'] not in excluded]
    provenance['cross_split_duplicate_images_excluded'] = sorted(excluded)
    maps = torch.from_numpy(np.load(CACHE / 'spatial_features.npz')['features'])
    spec = read_manifest(BASELINE)['classifiers']['eye']
    loaded = YOLO(str(artifact_path(BASELINE,spec['artifacts']['torch'])))
    loaded.model.cpu().float().eval()
    tail = loaded.model.model[-1]
    original = copy.deepcopy(tail).eval()
    # Begin with the first refined linear layer; the frozen trunk is unchanged.
    initial = Classifier(ROOT / 'models/eye_refined/manifest.json','eye','torch').model.model[-1].linear
    tail.linear.load_state_dict(initial.state_dict())
    for parameter in tail.parameters():
        parameter.requires_grad_(True)
    for parameter in original.parameters():
        parameter.requires_grad_(False)
    train_rows = [r for r in records if r['split'] == 'train']
    def group(row):
        return row['source'],row.get('dataset','legacy'),row['label']
    groups = Counter(group(r) for r in train_rows)
    indexes = torch.tensor([r['feature'] for r in train_rows])
    targets = torch.tensor([CLASSES.index(r['label']) for r in train_rows])
    weights = torch.tensor([len(train_rows) / (len(groups)*groups[group(r)]) for r in train_rows])
    optimizer = torch.optim.AdamW([{'params':tail.conv.parameters(),'lr':.0003},
                                  {'params':tail.linear.parameters(),'lr':.0005}],weight_decay=.0001)
    baseline_p = probabilities(original,maps)
    baseline = metrics(records,baseline_p,'val')
    diagnostic = [r['feature'] for r in records
                  if r['path'].endswith('positive/file0127.jpg') and r['variant'] == 'base']
    if len(diagnostic) != 2:
        raise ValueError('Missing both reviewed Open regression crops')
    trials, selected, best = [], None, -float('inf')
    for epoch in range(1,epochs+1):
        order = torch.randperm(len(train_rows))
        total_loss = 0.
        for offset in range(0,len(order),64):
            batch = order[offset:offset+64]
            optimizer.zero_grad(set_to_none=True)
            output_logits = logits(tail,maps[indexes[batch]].float())
            loss = (torch.nn.functional.cross_entropy(output_logits,targets[batch],reduction='none')*weights[batch]).mean()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()*len(batch)
        p = probabilities(tail,maps)
        val = metrics(records,p,'val')
        diagnostic_min = float(p[diagnostic,1].min())
        qualified = (diagnostic_min >= .8 and val['legacy']['macro_f1'] >= .98
            and val['legacy']['Closed_recall_ge_080'] >= .98
            and val['roi']['Open_recall_ge_080'] >= .9
            and val['roi']['Closed_recall_ge_080'] >= max(.9,baseline['roi']['Closed_recall_ge_080']-.02)
            and val['manual_roi']['Closed_recall_ge_080'] >= baseline['manual_roi']['Closed_recall_ge_080']-.02)
        score = (val['roi']['Open_recall_ge_080']+val['roi']['Closed_recall_ge_080']+val['legacy']['macro_f1'])/3
        trial = {'epoch':epoch,'loss':total_loss/len(train_rows),'score':score,
                 'diagnostic_open_min_probability':diagnostic_min,'qualified':bool(qualified),'metrics':val}
        trials.append(trial)
        print(json.dumps({k:v for k,v in trial.items() if k != 'metrics'}),flush=True)
        if qualified and score > best:
            best, selected = score,(copy.deepcopy(tail.state_dict()),trial)
    output.mkdir(parents=True,exist_ok=True)
    save(output/'validation.json',{'baseline':baseline,'trials':trials,'selected':selected[1] if selected else None})
    if selected is None:
        raise RuntimeError('No candidate meets eye regression AND true-closure validation; PC unchanged')
    tail.load_state_dict(selected[0])
    loaded.ckpt['train_metrics'],loaded.ckpt['train_results'] = {},{}
    loaded.ckpt['epoch'] = selected[1]['epoch']
    refinement = {'method':'freeze YOLO backbone; fine-tune Classify conv/BN affine/linear; fixed BN running statistics',
        'baseline_sha256':spec['artifacts']['torch']['sha256'],'labels_sha256':sha256(LABELS),
        'spatial_features_sha256':spatial['features_sha256'],
        'known_failure_split':next(r['split'] for r in records if r['feature'] == diagnostic[0]),
        'selection':'validation metrics with a known-bug regression guard; no test selection'}
    loaded.ckpt['refinement'] = refinement
    checkpoint = output/'best_eye.pt'
    loaded.save(checkpoint)
    detector = read_manifest(BASELINE)['detector']
    detector['file'] = os.path.relpath(artifact_path(BASELINE,detector),output).replace(os.sep,'/')
    save(output/'yunet.source.json',detector)
    smile = ROOT/'models/smile_refined/manifest.json'
    exported = export_models(output,checkpoint,artifact_path(smile,read_manifest(smile)['classifiers']['yawn']['artifacts']['torch']))
    contract = read_manifest(exported)
    contract['refinement'] = {'eye':refinement,'yawn':read_manifest(smile)['refinement']}
    contract['eye_roi'] = provenance['crop_config']
    contract['deployment_validation'] = 'PC development; labeled driver wink/closure videos and Radxa hardware pending'
    save(exported,contract)
    locked = Classifier(exported,'eye','torch').model.model[-1]
    p = probabilities(locked,maps)
    save(output/'evaluation.json',{'manifest_sha256':sha256(exported),'checkpoint_sha256':sha256(checkpoint),
        'type':'static_eye_tail_development_evaluation','selected_on_validation':selected[1],
        'provenance':{k:v for k,v in provenance.items() if k != 'records'},
        'test_baseline':metrics(records,baseline_p,'test'),'test_candidate':metrics(records,p,'test'),
        'evaluation_scope':'Prior manual/CEW tests are development audit after earlier candidate assessment; independent driver-video acceptance NOT measured'})
    print('Qualified candidate exported; camera profile not changed by training tool',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage',choices=('prepare','train'))
    parser.add_argument('--epochs',type=int,default=20)
    parser.add_argument('--output',type=Path,default=ROOT/'models/eye_refined_v3')
    parser.add_argument('--cache',type=Path,default=CACHE)
    parser.add_argument('--labels',type=Path,default=LABELS)
    args = parser.parse_args()
    CACHE,LABELS = args.cache.resolve(),args.labels.resolve()
    torch.manual_seed(42)
    torch.set_num_threads(2)
    prepare() if args.stage == 'prepare' else train(args.output.resolve(),args.epochs)
