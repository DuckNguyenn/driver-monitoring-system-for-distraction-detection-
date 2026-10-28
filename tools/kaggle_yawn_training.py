"""GPU training on a portable native-crop bundle. No local video or feature cache needed."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from collections import Counter
from dataclasses import asdict

import cv2
import numpy as np


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def locate_bundle(search_root='/kaggle/input'):
    matches = list(Path(search_root).rglob('bundle.json'))
    matches = [p for p in matches if json.loads(p.read_text()).get('kind') == 'driver_monitor_yawn_near_medium']
    if len(matches) != 1:
        raise ValueError('Add the extracted yawn_near_medium_dataset to this notebook; expected exactly one bundle.json.')
    return matches[0].parent


def load_bundle(root):
    root = Path(root).resolve()
    bundle = json.loads((root / 'bundle.json').read_text(encoding='utf-8'))
    if bundle.get('kind') != 'driver_monitor_yawn_near_medium' or bundle.get('schema_version') != 1:
        raise ValueError('unsupported training bundle')
    for name, expected in bundle['checksums'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or digest(path) != expected:
            raise ValueError(f'bundle file/checksum mismatch: {name}')
    sys.path.insert(0, str(root / 'support'))
    from driver_monitor.models import prepare_rgb
    data = json.loads((root / 'dataset.json').read_text(encoding='utf-8'))
    assignments = {}
    for row in data['records']:
        if row['label'] not in ('no_yawn', 'yawn') or row['split'] not in ('train', 'val'):
            raise ValueError('invalid labels/splits')
        path = (root / row['file']).resolve()
        if not path.is_relative_to(root) or digest(path) != row['sha256']:
            raise ValueError('native crop changed')
        rgb_hash = hashlib.sha256(prepare_rgb(cv2.imread(str(path)), data['runtime_spec']).tobytes()).hexdigest()
        if rgb_hash != row['input_sha256']:
            raise ValueError('preprocessing differs from the runtime')
        if rgb_hash in assignments and assignments[rgb_hash] != (row['split'], row['label']):
            raise ValueError('identical prepared pixels across splits or conflicting labels')
        assignments[rgb_hash] = (row['split'], row['label'])
        if row['domain'] == 'camera' and (row['distance'] not in ('near', 'medium') or row['split'] != 'train'):
            raise ValueError('camera scope/split changed')
    support = Counter((r['source'], r['label']) for r in data['records'] if r['split'] == 'val')
    for source, label in (('legacy', 'no_yawn'), ('legacy', 'yawn'), ('smiles', 'no_yawn'), ('genki', 'no_yawn')):
        if support[source, label] < 10:
            raise ValueError('insufficient retained static validation')
    return bundle, data


def seed_worker(worker_id):
    import torch
    info = torch.utils.data.get_worker_info()
    info.dataset.rng = np.random.default_rng(torch.initial_seed() % 2**32)


def gpu_probabilities(model, rows, root, spec, batch_size, device):
    import torch
    from driver_monitor.models import prepare_rgb, prepare_tensor
    from support_tools.finetune_yawn_distance import model_logits
    values = []
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            selected = rows[start:start+batch_size]
            x = np.concatenate([prepare_tensor(prepare_rgb(cv2.imread(str(root/r['file'])), spec), spec) for r in selected])
            values.extend(torch.softmax(model_logits(model, torch.from_numpy(x).to(device)), 1).float().cpu().numpy())
    return np.asarray(values, dtype=np.float32)


def train(root, output, *, start_from='usb_refined', epochs=40, batch_size=64,
          learning_rate=1e-4, camera_weight=.8, patience=8, seed=42, workers=2,
          amp=True, require_gpu=True):
    import torch
    if require_gpu and not torch.cuda.is_available():
        raise RuntimeError('GPU is disabled. Kaggle Settings > Accelerator > GPU, then restart the session.')
    from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
    from ultralytics import YOLO
    root, output = Path(root).resolve(), Path(output).resolve()
    bundle, data = load_bundle(root)
    from driver_monitor.models import prepare_tensor
    from driver_monitor.yawn_distance import DistanceAugmentation, training_rgb, json_save, CLASSES
    from support_tools.finetune_yawn_distance import configure_model, model_logits, grouped_metrics, validation_passed, selection_score
    if start_from not in bundle['checkpoints'] or min(epochs, batch_size, patience) < 1 or workers < 0:
        raise ValueError('invalid checkpoint/training settings')
    if not 0 < learning_rate <= .01 or not 0 < camera_weight < 1:
        raise ValueError('invalid learning rate/camera weight')
    if output.exists() and any(output.iterdir()):
        raise ValueError('output is nonempty; choose another output folder')
    output.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed); np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(2)
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    recipe = DistanceAugmentation(**data['augmentation'])
    spec = data['runtime_spec']
    training = [r for r in data['records'] if r['split'] == 'train' and r['train_eligible']]
    validation = [r for r in data['records'] if r['split'] == 'val']
    loaded = YOLO(str(root / bundle['checkpoints'][start_from]))
    if [loaded.names[i] for i in range(2)] != list(CLASSES):
        raise ValueError('checkpoint class order mismatch')
    count = configure_model(loaded.model)
    model = loaded.model.to(device)
    prefix = f'model.{len(model.model)-1}.'
    frozen = {k:v.detach().cpu().clone() for k,v in model.state_dict().items()
              if not k.startswith(prefix) or 'running_' in k or 'num_batches_tracked' in k}
    baseline = grouped_metrics(validation, gpu_probabilities(model, validation, root, spec, batch_size, device))

    class NativeCrops(Dataset):
        def __init__(self): self.rng = np.random.default_rng(seed)
        def __len__(self): return len(training)
        def __getitem__(self, index):
            row = training[index]
            rgb = training_rgb(cv2.imread(str(root / row['file'])), spec, 'train', recipe, self.rng)
            return torch.from_numpy(prepare_tensor(rgb, spec)[0]), CLASSES.index(row['label'])

    def group(r): return r['domain'], r['label'], r['distance'], r['action'], r['source']
    groups = Counter(group(r) for r in training)
    group_counts = Counter((g[0],g[1]) for g in groups)
    weights = [(camera_weight if r['domain'] == 'camera' else 1-camera_weight) /
               (2*group_counts[r['domain'],r['label']]*groups[group(r)]) for r in training]
    generator = torch.Generator().manual_seed(seed)
    sampler = WeightedRandomSampler(weights, min(len(training),2000), replacement=True, generator=generator)
    loader = DataLoader(NativeCrops(), sampler=sampler, batch_size=batch_size, num_workers=workers,
        worker_init_fn=seed_worker, generator=generator, pin_memory=device.type == 'cuda')
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=learning_rate, weight_decay=1e-4)
    use_amp = amp and device.type == 'cuda'
    scaler = torch.amp.GradScaler('cuda', enabled=use_amp)
    selected, best, stale, trials = None, -float('inf'), 0, []
    report = {'status':'training', 'validation_mode':'static_only', 'camera_validation_pending':True,
        'selection_split':'val', 'selection_domain':'static_only', 'test_used_for_selection':False,
        'event_acceptance_measured':False, 'active_distances':['near','medium'],
        'start_from': start_from, 'baseline_sha256': digest(root/bundle['checkpoints'][start_from]),
        'dataset_sha256':digest(root/'dataset.json'), 'trainable_parameters':count,
        'gpu':torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU smoke only',
        'torch_version':torch.__version__, 'python_version':sys.version,
        'numpy_version':np.__version__, 'baseline_validation':baseline, 'trials':trials,
        'parameters':{'epochs':epochs,'batch_size':batch_size,'learning_rate':learning_rate,
                      'camera_weight':camera_weight,'seed':seed,'workers':workers,'amp':use_amp}}
    for epoch in range(1, epochs+1):
        model.eval()  # Train affine/conv/linear with frozen backbone and BN running buffers.
        total_loss = samples = 0
        for x, y in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
                loss = torch.nn.functional.cross_entropy(model_logits(model,x),y)
            if not torch.isfinite(loss): raise RuntimeError('nonfinite loss; no candidate exported')
            scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update()
            total_loss += float(loss.detach()) * len(y); samples += len(y)
        candidate = grouped_metrics(validation, gpu_probabilities(model,validation,root,spec,batch_size,device))
        reasons = validation_passed(candidate,baseline,('near','medium'),'static_only')
        score = selection_score(candidate,('near','medium'),'static_only')
        trial = {'epoch':epoch,'loss':total_loss/samples,'score':score,'rejection_reasons':reasons,'validation':candidate}
        trials.append(trial)
        if not reasons and score > best:
            best, stale = score, 0
            selected = ({k:v.detach().cpu().clone() for k,v in model.state_dict().items()}, trial)
        else: stale += 1
        print(json.dumps({k:v for k,v in trial.items() if k != 'validation'}), flush=True)
        json_save(output/'validation.json', report)
        if selected is not None and stale >= patience: break
    report['selected'] = selected[1] if selected else None
    if selected is None:
        report['status']='rejected'; json_save(output/'validation.json',report)
        raise RuntimeError('No checkpoint passed static validation. See validation.json; do not deploy.')
    model.load_state_dict(selected[0]); model.cpu().float().eval()
    report['frozen_backbone_and_bn_buffers_unchanged'] = all(torch.equal(model.state_dict()[k],v) for k,v in frozen.items())
    if not report['frozen_backbone_and_bn_buffers_unchanged']: raise RuntimeError('Frozen tensors changed')
    loaded.ckpt.update(train_metrics={},train_results={},epoch=selected[1]['epoch'])
    loaded.save(output/'candidate_yawn.pt')
    serialized = YOLO(str(output/'candidate_yawn.pt')).model.cpu().float().eval()
    measured = grouped_metrics(validation,gpu_probabilities(serialized,validation,root,spec,batch_size,torch.device('cpu')))
    report['serialized_validation'] = measured
    report['serialized_rejection_reasons'] = validation_passed(measured,baseline,('near','medium'),'static_only')
    if report['serialized_rejection_reasons']:
        report['status']='serialized_rejected'; json_save(output/'validation.json',report)
        raise RuntimeError('Serialized weights failed validation; no deployment bundle exported')
    (output/'candidate_yawn.pt').replace(output/'best_yawn.pt')
    report['status']='experimental_static_validation_only'
    json_save(output/'validation.json',report)
    export_result(root, output, data, report)
    return report


def export_result(root, output, data, report):
    import torch
    import onnx
    import onnxruntime as ort
    import yaml
    from ultralytics import YOLO
    from driver_monitor.models import prepare_rgb, prepare_tensor
    from driver_monitor.yawn_distance import json_save
    from support_tools.finetune_yawn_distance import model_logits
    root, output = Path(root), Path(output)
    spec = data['runtime_spec']
    model = YOLO(str(output/'best_yawn.pt')).model.cpu().float().eval()
    model.model[-1].export = True
    torch.onnx.export(model,torch.zeros(1,3,224,224),str(output/'best_yawn.onnx'),
        input_names=['images'],output_names=['probabilities'],opset_version=12,dynamo=False)
    graph = onnx.load(output/'best_yawn.onnx')
    onnx.checker.check_model(graph)
    if graph.ir_version > 10:
        raise RuntimeError('Exported ONNX IR is newer than the PC runtime supports; do not deploy')
    model.model[-1].export = False
    opts = ort.SessionOptions(); opts.intra_op_num_threads=2; opts.inter_op_num_threads=1
    session = ort.InferenceSession(str(output/'best_yawn.onnx'),opts,providers=['CPUExecutionProvider'])
    chosen = []
    for domain, split, distance in (('camera','train','near'),('camera','train','medium'),('static','val','unspecified')):
        for label in ('no_yawn','yawn'):
            rows = [r for r in data['records'] if (r['domain'],r['split'],r['distance'],r['label']) == (domain,split,distance,label)]
            if rows: chosen.extend(rows[i] for i in np.linspace(0,len(rows)-1,min(8,len(rows)),dtype=int))
    deltas = []
    with torch.inference_mode():
        for row in chosen:
            x = prepare_tensor(prepare_rgb(cv2.imread(str(root/row['file'])),spec),spec)
            a = torch.softmax(model_logits(model,torch.from_numpy(x)),1).numpy()
            b = session.run(None,{'images':x})[0]
            deltas.append(float(np.max(np.abs(a-b))))
    parity = {'samples':len(deltas),'max_probability_delta':max(deltas),'passed':max(deltas)<=1e-4,
        'onnx_ir_version':graph.ir_version, 'onnx_opsets':{op.domain or 'ai.onnx':op.version for op in graph.opset_import},
        'onnx_version':onnx.__version__, 'onnxruntime_version':ort.__version__}
    json_save(output/'parity.json',parity)
    if not parity['passed']: raise RuntimeError('PT/ONNX parity failed; do not deploy')
    contract = json.loads((root/'base_manifest.json').read_text(encoding='utf-8'))
    contract['classifiers']['yawn']['artifacts'] = {backend:{'file':f'best_yawn.{ext}','sha256':digest(output/f'best_yawn.{ext}')}
        for backend,ext in (('torch','pt'),('onnx','onnx'))}
    contract.setdefault('refinement',{})['yawn'] = {
        'method':'Kaggle GPU Classify conv/BN affine/Linear fine-tune; frozen backbone/BN buffers',
        'baseline_sha256':report['baseline_sha256'],'start_from':report['start_from'],
        'dataset_sha256':report['dataset_sha256'],'training_augmentation':data['augmentation'],
        'augmentation_at_inference':False,'active_distances':['near','medium'],
        'validation_mode':'static_only','camera_validation_pending':True,
        'selection_split':'val','test_used_for_selection':False}
    contract['deployment_validation']='Experimental: retained static validation only; new camera/person/event/Radxa acceptance pending'
    json_save(output/'manifest.json',contract)
    runtime = json.loads((root/'runtime_settings.json').read_text(encoding='utf-8'))
    runtime.update(manifest='manifest.json',backend='onnx',log_dir='../../logs')
    (output/'runtime.yaml').write_text(yaml.safe_dump(runtime,sort_keys=False),encoding='utf-8')
    (output/'README.txt').write_text('Extract this folder under DA2/models/. Requires the existing eye/YuNet artifacts.\n'
        'Experimental near/medium yawn weights. Static validation is not independent camera acceptance.\n',encoding='utf-8')
