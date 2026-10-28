"""Portable native crops keep exact preprocessing, GPU requirement and export contract."""
import ast
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

import cv2
import numpy as np

from driver_monitor.config import ROOT, load_config
from driver_monitor.models import prepare_rgb, read_manifest
from tools.build_yawn_kaggle_bundle import notebook
from tools.kaggle_yawn_training import load_bundle, locate_bundle, train


class KaggleBundleTests(unittest.TestCase):
    def bundle(self, directory):
        root = Path(directory)
        spec = read_manifest(ROOT/'models/yawn_usb_robust/manifest.json')['classifiers']['yawn']
        records = []
        for i,(source,label) in enumerate((('legacy','no_yawn'),('legacy','yawn'),('smiles','no_yawn'),('genki','no_yawn'))):
            crop = np.random.default_rng(5+i).integers(0,256,(131,97,3),dtype=np.uint8)
            path = root/f'crop_{i}.png'; cv2.imwrite(str(path),crop)
            row = {'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'input_sha256':hashlib.sha256(prepare_rgb(crop,spec).tobytes()).hexdigest(),
                'label':label,'domain':'static','source':source,'split':'val','distance':'unspecified'}
            records.extend({**row,'source':source,'label':label} for _ in range(10))
        data = {'runtime_spec':spec,'records':records}
        (root/'dataset.json').write_text(json.dumps(data))
        bundle = {'schema_version':1,'kind':'driver_monitor_yawn_near_medium', 'checkpoints':{},
            'checksums':{name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                for name in ('dataset.json','crop_0.png','crop_1.png','crop_2.png','crop_3.png')}}
        (root/'bundle.json').write_text(json.dumps(bundle))
        return root

    def test_notebook_cells_compile_and_require_cuda_not_cpu_fallback(self):
        nb = notebook()
        self.assertEqual(nb['nbformat'],4)
        for cell in nb['cells']:
            if cell['cell_type']=='code':
                source = ''.join(cell['source'])
                ast.parse(source)
                self.assertFalse(cell['outputs'])
        text = '\n'.join(''.join(c['source']) for c in nb['cells'])
        self.assertIn('require_gpu=True',text)
        self.assertIn("START_FROM = 'usb_refined'",text)
        self.assertIn('original_kaggle',text)
        self.assertNotIn('.train(data=',text)

    def test_portable_bundle_checks_pixels_and_rejects_tampering_and_scope_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.bundle(directory)
            bundle,data = load_bundle(root)
            self.assertEqual(locate_bundle(root),root)
            data['records'][0].update(domain='camera',distance='far',split='train')
            (root/'dataset.json').write_text(json.dumps(data))
            bundle['checksums']['dataset.json'] = hashlib.sha256((root/'dataset.json').read_bytes()).hexdigest()
            (root/'bundle.json').write_text(json.dumps(bundle))
            with self.assertRaisesRegex(ValueError,'scope/split'):
                load_bundle(root)
            (root/'crop_0.png').write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError,'checksum'):
                load_bundle(root)

    def test_gpu_disabled_fails_before_model_loading_or_output_creation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = self.bundle(directory)
            with patch('torch.cuda.is_available', return_value=False):
                with self.assertRaisesRegex(RuntimeError,'GPU is disabled'):
                    train(root,root/'result',require_gpu=True)
            self.assertFalse((root/'result').exists())


if __name__ == '__main__':
    unittest.main()
