"""Verify GPU artifacts through the actual PC runtime, without retraining or tuning."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', type=Path, default=ROOT / 'models/multiview_20261013')
    parser.add_argument('--dataset', type=Path, default=ROOT / 'kaggle_upload/multiview_20261013')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/multiview_20261013/pc_verification.json')
    args = parser.parse_args()
    import cv2
    import numpy as np
    import torch
    import onnxruntime
    from driver_monitor.models import Classifier, read_manifest, sha256
    from driver_monitor.multiview_learning import evaluate
    data = json.loads((args.dataset / 'dataset.json').read_text(encoding='utf-8'))
    manifest = args.models / 'manifest.json'
    read_manifest(manifest)
    result = {'torch': torch.__version__, 'onnxruntime': onnxruntime.__version__,
              'numpy': np.__version__, 'manifest_sha256': sha256(manifest), 'tasks': {}}
    for name in ('eye', 'yawn'):
        onnx_model = Classifier(manifest, name, 'onnx')
        torch_model = Classifier(manifest, name, 'torch')
        rows = [row for row in data['records'] if row['task'] == name and row['split'] == 'test']
        report = json.loads((args.models / f'{name}_evaluation.json').read_text(encoding='utf-8'))
        predictions, differences, mismatches = [], [], 0
        parity_indices = set(np.linspace(0, len(rows) - 1, min(32, len(rows)), dtype=int).tolist())
        for index, row in enumerate(rows):
            image = cv2.imread(str(args.dataset / row['file']))
            assert image is not None, row['file']
            onnx_p = onnx_model.predict(image)
            values = [onnx_p[label] for label in onnx_model.spec['classes']]
            predictions.append(values)
            if index in parity_indices:
                torch_p = torch_model.predict(image)
                differences.append(max(abs(onnx_p[label] - torch_p[label]) for label in onnx_p))
                mismatches += max(onnx_p, key=onnx_p.get) != max(torch_p, key=torch_p.get)
        metric = evaluate(rows, np.asarray(predictions), name)
        cloud_delta = float(np.max(np.abs(np.asarray(predictions) - np.asarray([p['candidate'] for p in report['heldout_predictions']]))))
        for group, actual in metric['groups'].items():
            expected = report['heldout_camera']['candidate']['groups'][group]
            assert actual['confusion_matrix'] == expected['confusion_matrix'], group
            assert actual['confidence_and_quality_gate']['confusion_matrix_with_unknown'] == expected['confidence_and_quality_gate']['confusion_matrix_with_unknown'], group
        maximum = max(differences)
        assert maximum <= 1e-4 and mismatches == 0, 'PC PT/ONNX parity failed'
        result['tasks'][name] = {'parity_samples': len(differences), 'max_probability_delta': maximum,
                                 'label_mismatches': mismatches, 'passed': True,
                                 'max_cloud_gpu_to_pc_probability_delta': cloud_delta,
                                 'parameter_count': sum(p.numel() for p in torch_model.model.parameters()),
                                 'architecture_layers': [type(layer).__name__ for layer in torch_model.model.model],
                                 'pc_metrics': metric,
                                 'artifacts': read_manifest(manifest)['classifiers'][name]['artifacts']}
        onnx_model.close()
        torch_model.close()
        print(name, 'PC parity passed', maximum, 'GPU/PC delta', cloud_delta, flush=True)
    from driver_monitor.config import load_config
    from driver_monitor.runtime import run
    video = Path(r'C:\Users\P1 Gen 5\Pictures\Camera Roll\WIN_20261013_17_07_01_Pro.mp4')
    settings = load_config(args.models / 'runtime.yaml', headless=True, max_frames=20, serial_port=None,
                           log_dir=args.output.parent / 'integration_logs')
    result['integration_smoke'] = run(settings, str(video))
    assert result['integration_smoke']['frames'] == 20 and result['integration_smoke']['fault'] is None
    result['live_camera_acceptance'] = False
    result['event_accuracy'] = None
    result['note'] = 'PC inference parity and 20-frame integration only; not a live-camera benchmark or acceptance.'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
