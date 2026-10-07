"""Refine the final eye-classifier layer on manually reviewed runtime crops.

Preserve both true Closed and Open classes, select only on validation, and
export a separate candidate. Static development splits do not establish
person-independent camera accuracy. Smile/yawn labels are never eye labels.
"""
import argparse
import copy
import hashlib
import json
import os
import re
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
from driver_monitor.evaluation import classification_metrics, image_samples
from driver_monitor.exporting import export_models
from driver_monitor.models import Classifier, artifact_path, prepare_rgb, prepare_tensor, read_manifest, sha256
from driver_monitor.vision import Vision

CACHE = ROOT / '.cache/eye_refinement'
LABELS = ROOT / 'data_reviews/eye_roi_labels.json'
BASELINE = ROOT / 'models/manifest.json'
CLASSES = ['Closed', 'Open']
INCLUDE_CEW = False


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def augment(image):
    """Training-only variants, applied equally to both eye classes."""
    yield 'base', image
    yield 'mirror', cv2.flip(image, 1)
    yield 'gray', cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    yield 'dim', np.clip(image.astype(np.float32) * .70, 0, 255).astype(np.uint8)
    h, w = image.shape[:2]
    for angle in (-8, 8):
        transform = cv2.getRotationMatrix2D((w/2, h/2), angle, 1)
        yield f'roll{angle}', cv2.warpAffine(image, transform, (w, h), borderMode=cv2.BORDER_REPLICATE)


def prepare():
    config = load_config(ROOT / 'configs/camera_pc.yaml', manifest=BASELINE)
    spec = read_manifest(BASELINE)['classifiers']['eye']
    model = Classifier(BASELINE, 'eye', 'torch').model
    vectors, records, pending, metadata, caught = [], [], [], [], []
    if INCLUDE_CEW:
        old = ROOT / '.cache/eye_refinement'
        cached = json.loads((old / 'records.json').read_text())
        if (cached['labels_sha256'] != sha256(LABELS) or cached['baseline_manifest_sha256'] != sha256(BASELINE)
                or cached['features_sha256'] != sha256(old / 'features.npz')):
            raise ValueError('Original feature cache changed')
        vectors.extend(np.load(old / 'features.npz')['features'])
        records.extend(cached['records'])
    hook = model.model[-1].linear.register_forward_pre_hook(
        lambda module, inputs: caught.append(inputs[0].detach().numpy().copy()))
    CACHE.mkdir(parents=True, exist_ok=True)

    def flush():
        if not pending:
            return
        caught.clear()
        with torch.inference_mode():
            model(torch.from_numpy(np.concatenate(pending)))
        for row, vector in zip(metadata, caught[0]):
            records.append({**row, 'feature': len(vectors)})
            vectors.append(vector)
        pending.clear()
        metadata.clear()

    def add(image, row):
        rgb = prepare_rgb(image, spec)
        pending.append(prepare_tensor(rgb, spec))
        metadata.append({**row, 'input_sha256': hashlib.sha256(rgb.tobytes()).hexdigest()})
        if len(pending) == 16:
            flush()

    for split in (() if INCLUDE_CEW else ('train', 'val', 'test')):
        for path, label in image_samples(ROOT / 'kaggle_output/data/eye_dataset', split):
            image = cv2.imread(str(path))
            row = {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha256(path), 'label': label,
                   'split': split, 'source': 'legacy', 'variant': 'base'}
            add(image, row)
            if split == 'train':
                gray = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
                add(gray, {**row, 'variant': 'gray'})
        print(f'Legacy {split} prepared', flush=True)
    annotations = json.loads(LABELS.read_text(encoding='utf-8'))
    for row in ([] if INCLUDE_CEW else annotations['records']):
        if row['split'] not in ('train', 'val', 'test'):
            raise ValueError('Invalid reviewed split')
        path = ROOT / row['path']
        if sha256(path) != row['sha256']:
            raise ValueError(f'Review image changed: {path}')
        result = Vision(config).observe(cv2.imread(str(path)))
        if result.quality != 'usable' or [list(b) for b in result.boxes[:2]] != row['eye_boxes']:
            raise ValueError(f'Crop geometry/quality changed; review labels again: {path}')
        for eye, label in enumerate(row['eye_labels']):
            if label == 'Unknown':
                continue
            if label not in CLASSES:
                raise ValueError('Invalid per-eye label')
            base = {'path': row['path'], 'sha256': row['sha256'], 'label': label,
                    'split': row['split'], 'source': 'roi', 'dataset': row['source'], 'eye_index': eye}
            variants = augment(result.crops[eye]) if row['split'] == 'train' else [('base', result.crops[eye])]
            for variant, image in variants:
                add(image, {**base, 'variant': variant})
    cew_provenance = None
    if INCLUDE_CEW:
        source = ROOT / '.cache/cew/source.json'
        cew_provenance = json.loads(source.read_text())
        counts = Counter()
        limits = {'train':200, 'val':50, 'test':60}
        # All variants/faces from the same original photo stay in one split.
        for path in sorted((ROOT / '.cache/cew/faces/dataset_B_FacialImages_highResolution').glob('*.jpg')):
            family = re.match(r'closed_eye_(\d+)', path.name).group(1)
            bucket = int(hashlib.sha256(family.encode()).hexdigest()[:8], 16) % 100
            split = 'train' if bucket < 70 else 'val' if bucket < 85 else 'test'
            if counts[split] >= limits[split]:
                continue
            result = Vision(config).observe(cv2.imread(str(path)))
            if result.quality != 'usable':
                continue
            base = {'path':path.relative_to(ROOT).as_posix(), 'sha256':sha256(path), 'source':'roi',
                'dataset':'cew', 'photo_family':family, 'split':split, 'label':'Closed'}
            for eye in (0,1):
                variants = augment(result.crops[eye]) if split == 'train' else [('base', result.crops[eye])]
                for variant, image in variants:
                    add(image, {**base, 'eye_index':eye, 'variant':variant})
            counts[split] += 1
            if sum(counts.values()) % 50 == 0:
                print(f'CEW faces: {dict(counts)}',flush=True)
        if any(counts[s] < limits[s] for s in limits):
            raise ValueError(f'Insufficient usable CEW faces: {counts}')
    flush()
    hook.remove()
    matrix = np.stack(vectors).astype(np.float32)
    np.savez_compressed(CACHE / 'features.npz', features=matrix)
    save(CACHE / 'records.json', {'records': records, 'labels_sha256': sha256(LABELS),
         'baseline_manifest_sha256': sha256(BASELINE), 'features_sha256': sha256(CACHE / 'features.npz'),
         'crop_config': annotations['crop_config'], 'subject_independence': annotations['subject_independence'],
         'cew_source':cew_provenance,
         'prior_manual_test': 'Used to identify the initial candidate sensitivity regression; now a development audit, not an independent final test' if INCLUDE_CEW else None})
    print(json.dumps({'features': list(matrix.shape), 'counts': dict(Counter(
        f"{r['source']}/{r['split']}/{r['label']}/{r['variant']}" for r in records))}), flush=True)


def metrics(records, probabilities, split):
    report = {}
    for source in ('legacy', 'roi', 'manual_roi', 'cew_roi'):
        rows = [r for r in records if r['source'] == ('roi' if source.endswith('_roi') else source)
                and (source not in ('manual_roi','cew_roi') or (r.get('dataset') == 'cew') == (source == 'cew_roi'))
                and r['split'] == split and r['variant'] == 'base']
        truth = [r['label'] for r in rows]
        predicted = [CLASSES[int(probabilities[r['feature']].argmax())] for r in rows]
        result = classification_metrics(truth, predicted, CLASSES)
        for label in CLASSES:
            selected = [r for r in rows if r['label'] == label]
            result[f'{label}_recall_ge_080'] = sum(probabilities[r['feature'], CLASSES.index(label)] >= .8
                for r in selected) / max(1, len(selected))
        result['false_closed_ge_080'] = int(sum(r['label'] == 'Open' and probabilities[r['feature'], 0] >= .8 for r in rows))
        result['confident_coverage_ge_080'] = sum(probabilities[r['feature']].max() >= .8 for r in rows) / max(1, len(rows))
        report[source] = result
    return report


def train(output):
    provenance = json.loads((CACHE / 'records.json').read_text())
    if provenance['labels_sha256'] != sha256(LABELS) or provenance['baseline_manifest_sha256'] != sha256(BASELINE) or provenance['features_sha256'] != sha256(CACHE / 'features.npz'):
        raise ValueError('Stale feature cache; rerun prepare')
    priority = {'train': 0, 'val': 1, 'test': 2}
    raw = provenance['records']
    owners = {}
    for row in raw:
        for digest in (row['sha256'], row['input_sha256']):
            owners[digest] = max(owners.get(digest, -1), priority[row['split']])
    excluded = {r['path'] for r in raw if any(priority[r['split']] < owners[d]
                for d in (r['sha256'], r['input_sha256']))}
    records = [r for r in raw if r['path'] not in excluded]
    provenance['cross_split_duplicate_images_excluded'] = sorted(excluded)
    features = torch.from_numpy(np.load(CACHE / 'features.npz')['features'])
    spec = read_manifest(BASELINE)['classifiers']['eye']
    loaded = YOLO(str(artifact_path(BASELINE, spec['artifacts']['torch'])))
    loaded.model.cpu().float().eval()
    original = copy.deepcopy(loaded.model.model[-1].linear)
    for parameter in original.parameters():
        parameter.requires_grad_(False)
    with torch.no_grad():
        baseline_p = torch.softmax(original(features), 1).numpy()
    baseline = metrics(records, baseline_p, 'val')
    rows = [r for r in records if r['split'] == 'train']
    groups = Counter((r['source'], r['label']) for r in rows)
    indexes = torch.tensor([r['feature'] for r in rows])
    targets = torch.tensor([CLASSES.index(r['label']) for r in rows])
    weights = torch.tensor([1 / groups[r['source'], r['label']] for r in rows])
    weights /= weights.sum()
    x = features[indexes]
    selected, trials, best = None, [], -float('inf')
    for regularization in (0., .001, .01, .1):
        head = copy.deepcopy(original)
        for parameter in head.parameters():
            parameter.requires_grad_(True)
        optimizer = torch.optim.Adam(head.parameters(), lr=.005)
        for epoch in range(1, 201):
            optimizer.zero_grad(set_to_none=True)
            loss = (torch.nn.functional.cross_entropy(head(x), targets, reduction='none') * weights).sum()
            penalty = sum((p-q).square().sum() for p,q in zip(head.parameters(), original.parameters()))
            (loss + regularization * penalty).backward()
            optimizer.step()
            if epoch not in (25,50,100,150,200):
                continue
            with torch.no_grad():
                p = torch.softmax(head(features), 1).numpy()
            val = metrics(records, p, 'val')
            qualified = (val['legacy']['macro_f1'] >= max(.9, baseline['legacy']['macro_f1'] - .02)
                and val['legacy']['Closed_recall_ge_080'] >= baseline['legacy']['Closed_recall_ge_080'] - .02
                and val['roi']['Closed_recall_ge_080'] >= max(.9, baseline['roi']['Closed_recall_ge_080'] - .02)
                and val['manual_roi']['Closed_recall_ge_080'] >= max(.8, baseline['manual_roi']['Closed_recall_ge_080'] - .02)
                and val['roi']['Open_recall_ge_080'] >= .90)
            score = (val['roi']['Open_recall_ge_080'] + val['roi']['Closed_recall_ge_080'] + val['legacy']['macro_f1']) / 3
            trial = {'regularization': regularization, 'epoch': epoch, 'score': score,
                     'preserves_validation_closed': bool(qualified), 'metrics': val}
            trials.append(trial)
            print(json.dumps({k:v for k,v in trial.items() if k != 'metrics'}), flush=True)
            if qualified and score > best:
                best, selected = score, (copy.deepcopy(head.state_dict()), trial)
    output.mkdir(parents=True, exist_ok=True)
    save(output / 'validation.json', {'baseline': baseline, 'trials': trials, 'selected': selected[1] if selected else None})
    if selected is None:
        raise RuntimeError('No candidate preserves closed-eye validation; PC model unchanged')
    loaded.model.model[-1].linear.load_state_dict(selected[0])
    loaded.ckpt['train_metrics'], loaded.ckpt['train_results'] = {}, {}
    loaded.ckpt['epoch'] = selected[1]['epoch']
    refinement = {'method': 'frozen backbone/classifier convolution; train final linear only',
        'baseline_sha256': spec['artifacts']['torch']['sha256'], 'labels_sha256': sha256(LABELS),
        'records_sha256': sha256(CACHE / 'records.json'), 'selection': 'validation only; no test selection',
        'regularization': selected[1]['regularization']}
    loaded.ckpt['refinement'] = refinement
    checkpoint = output / 'best_eye.pt'
    loaded.save(checkpoint)
    detector = read_manifest(BASELINE)['detector']
    detector['file'] = os.path.relpath(artifact_path(BASELINE, detector), output).replace(os.sep, '/')
    save(output / 'yunet.source.json', detector)
    # Keep the already validated smile-refined yawn checkpoint.
    smile = ROOT / 'models/smile_refined/manifest.json'
    yawn = artifact_path(smile, read_manifest(smile)['classifiers']['yawn']['artifacts']['torch'])
    exported = export_models(output, checkpoint, yawn)
    contract = read_manifest(exported)
    contract['deployment_validation'] = 'static per-eye development refinement; driver videos and Radxa hardware pending'
    contract['refinement'] = {'eye': refinement, 'yawn': read_manifest(smile)['refinement']}
    contract['eye_roi'] = provenance['crop_config']
    save(exported, contract)
    locked = Classifier(exported, 'eye', 'torch').model.model[-1].linear
    with torch.no_grad():
        candidate_p = torch.softmax(locked(features), 1).numpy()
    report = {'type': 'static_manually_reviewed_eye_development_evaluation',
        'manifest_sha256': sha256(exported), 'checkpoint_sha256': sha256(checkpoint),
        'provenance': {k:v for k,v in provenance.items() if k != 'records'},
        'selected_on_validation': selected[1], 'test_baseline': metrics(records, baseline_p, 'test'),
        'test_candidate': metrics(records, candidate_p, 'test'),
        'camera_event_acceptance': 'not measured; subject/clip separation NOT established',
        'evaluation_scope': 'CEW test photo families held out; prior manual test is now a development audit' if INCLUDE_CEW else 'Initial manual development split'}
    save(output / 'evaluation.json', report)
    print(json.dumps({k:report[k] for k in ('test_baseline','test_candidate')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('prepare','train'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--include-cew', action='store_true', help='Add official Closed-Eyes-in-the-Wild faces; reuse frozen baseline features')
    args = parser.parse_args()
    INCLUDE_CEW = args.include_cew
    if INCLUDE_CEW:
        CACHE = ROOT / '.cache/eye_refinement_v2'
    output = args.output or ROOT / ('models/eye_refined_v2' if INCLUDE_CEW else 'models/eye_refined')
    torch.set_num_threads(2)
    torch.manual_seed(42)
    prepare() if args.stage == 'prepare' else train(output.resolve())
