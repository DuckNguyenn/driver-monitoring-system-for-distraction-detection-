"""Build private-upload native dataset + GPU notebook from verified prepared crops."""
import copy
import json
import os
from pathlib import Path
import sys
import zipfile
from collections import Counter
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from driver_monitor.config import load_config
from driver_monitor.models import artifact_path, read_manifest, sha256
from driver_monitor.yawn_distance import json_save, verify_prepared_dataset
from tools.finetune_yawn_distance import checked_annotations, options


REQUIREMENTS = '''# Keep Kaggle's CUDA-enabled torch/torchvision; do not replace them with CPU wheels.
ultralytics==8.4.163
onnx==1.17.0; python_version < "3.13"
onnx==1.19.1; python_version >= "3.13"
onnxruntime==1.20.1; python_version < "3.13"
onnxruntime==1.23.2; python_version >= "3.13"
numpy==1.26.4; python_version < "3.13"
numpy==2.2.6; python_version >= "3.13"
Pillow==11.1.0
opencv-python==4.11.0.86
'''


def notebook():
    cells = []
    def md(text): cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(True)})
    def code(text): cells.append({'cell_type':'code','metadata':{},'execution_count':None,'outputs':[], 'source':text.splitlines(True)})
    md('''# Fine-tune YOLOv8n-cls ngáp trên Kaggle GPU: gần và trung bình

Dataset là **native crop mặt từ runtime YuNet**, không phải ảnh chụp màn hình. Có 255 crop camera train, 320 ảnh static train và 160 ảnh static validation. Hai clip camera đều là train, cùng một người/buổi thu. Không có camera validation mới hoặc test độc lập trong gói này.

Chỉ Classify conv + BN affine + Linear được cập nhật; backbone và BN running buffers cố định. Downsampling/Gaussian/motion blur diễn ra **trước** RGB/resize/center crop 224×224. Validation giữ nguyên pixel/preprocessing runtime. Không dùng `YOLO.train()` mặc định vì transform mặc định khác quy trình dự án.

1. Tạo Kaggle Dataset **Private** từ `yawn_near_medium_dataset.zip`.
2. Import notebook này, Add Input dataset vừa tạo.
3. Settings → Accelerator → GPU (T4/P100 hoặc GPU đang có); bật Internet cho bước cài thư viện.
4. Run All. Cell GPU sẽ dừng ngay nếu chưa bật CUDA.

GPU tăng tốc huấn luyện; không thay thế dữ liệu đa góc/độc lập. Bản CPU thử trước đã học tốt hai clip train nhưng bỏ sót clip USB góc thấp cũ, nên checkpoint trong notebook tiếp tục mang nhãn **thử nghiệm**, chưa tự thay profile chính.

Nguồn hướng dẫn Kaggle: https://www.kaggle.com/docs/notebooks. Không gửi notebook/dataset lên Kaggle tự động.
''')
    code('''import os, sys, subprocess
from pathlib import Path
from importlib.metadata import version
assert (3, 9) <= sys.version_info[:2] < (3, 14), 'Profile hỗ trợ Python 3.9–3.13; cần kiểm tra wheel cho phiên bản mới.'
os.environ['YOLO_CONFIG_DIR'] = '/kaggle/working/.config/ultralytics'
os.environ['MPLCONFIGDIR'] = '/kaggle/working/.config/matplotlib'
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
requirements = Path('/kaggle/working/requirements-kaggle.lock.txt')
requirements.write_text(__DEPENDENCY_REQUIREMENTS__, encoding='utf-8')
# Chỉ đọc metadata: chưa import NumPy/torch trước khi cài dependency.
constraints = Path('/kaggle/working/gpu-stack-constraints.txt')
constraints.write_text(''.join(f'{name}=={version(name)}\\n' for name in ('torch', 'torchvision')), encoding='utf-8')
print('Python:', sys.version, '| CUDA stack:', constraints.read_text(), flush=True)
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--quiet',
    '--only-binary=:all:', '-c', str(constraints), '-r', str(requirements)])
'''.replace('__DEPENDENCY_REQUIREMENTS__', repr(REQUIREMENTS)))
    md('## Kiểm tra GPU và tìm dataset (không cần sửa đường dẫn theo tên tài khoản)')
    code('''import torch, json, zipfile
assert torch.cuda.is_available(), 'Bật Settings > Accelerator > GPU rồi khởi động lại session.'
print('GPU:', torch.cuda.get_device_name(0), '| Torch:', torch.__version__)
torch.backends.cudnn.benchmark = False
torch.use_deterministic_algorithms(True, warn_only=True)

roots = list(Path('/kaggle/input').rglob('bundle.json'))
if not roots:
    archives = list(Path('/kaggle/input').rglob('yawn_near_medium_dataset.zip'))
    assert len(archives) == 1, 'Add Input dataset yawn_near_medium_dataset trước.'
    extracted = Path('/kaggle/working/native_dataset'); extracted.mkdir(exist_ok=True)
    with zipfile.ZipFile(archives[0]) as archive:
        assert all((extracted/n).resolve().is_relative_to(extracted.resolve()) for n in archive.namelist()), 'Unsafe ZIP path'
        archive.extractall(extracted)
    roots = list(extracted.rglob('bundle.json'))
roots = [p for p in roots if json.loads(p.read_text()).get('kind') == 'driver_monitor_yawn_near_medium']
assert len(roots) == 1, 'Giữ đúng một phiên bản dataset trong Input.'
DATA_ROOT = roots[0].parent
sys.path.insert(0, str(DATA_ROOT))
from kaggle_yawn_training import load_bundle, train
BUNDLE, DATA = load_bundle(DATA_ROOT)
print('Đã xác minh checksum và preprocessing:', DATA_ROOT)
''')
    md('## Kiểm tra nhãn, split và hình ảnh augmentation')
    code('''from collections import Counter
import cv2, matplotlib.pyplot as plt
from driver_monitor.yawn_distance import DistanceAugmentation, preview_views
print(Counter((r['domain'], r['split'], r['label']) for r in DATA['records']))
print('Class order:', DATA['runtime_spec']['classes'])
print('Camera validation: CHƯA CÓ; test độc lập: CHƯA CÓ')
recipe = DistanceAugmentation(**DATA['augmentation'])
sample = next(r for r in DATA['records'] if r['domain']=='camera' and r['distance']=='medium' and r['label']=='yawn')
native = cv2.imread(str(DATA_ROOT/sample['file']))
views = preview_views(native, DATA['runtime_spec'], recipe)
fig, axes = plt.subplots(2, 4, figsize=(14, 7))
for axis, (name, rgb) in zip(axes.flat, views.items()):
    axis.imshow(rgb); axis.set_title(name); axis.axis('off')
fig.suptitle(f"Native ROI {native.shape[1]}×{native.shape[0]} → train augmentation → 224×224")
plt.tight_layout(); plt.show()
''')
    md('''## Tham số fine-tune

Mặc định dùng bản USB refined (`usb_refined`) kế thừa model Kaggle gốc của bạn. Có thể đổi `START_FROM = 'original_kaggle'` để bắt đầu trực tiếp từ `camera_classical/best_yawn.pt` ban đầu. **Không dùng bản CPU candidate vừa train làm checkpoint khởi đầu.**

Batch 64 dùng GPU; giảm xuống 32/16 nếu hết VRAM. T4 ×2 chỉ dùng GPU đầu tiên ở bản này. Checkpoint chọn theo static validation, với guard không suy giảm F1/recall và ngáp nhầm so với chính checkpoint khởi đầu. Không dùng camera train để chọn weights. Ảnh cười/GENKI chỉ có lớp âm nên xem false-yawn, không diễn giải macro-F1 hai lớp riêng của chúng thành chất lượng toàn model.
''')
    code('''START_FROM = 'usb_refined'  # hoặc 'original_kaggle'
EPOCHS = 40
BATCH_SIZE = 64
LEARNING_RATE = 1e-4
CAMERA_WEIGHT = 0.80
PATIENCE = 8
SEED = 42
NUM_WORKERS = 2
AMP = True
OUT = Path('/kaggle/working/yawn_kaggle_near_medium')
# Nếu chạy lại trong cùng session, đổi OUT sang tên mới; tool không xóa kết quả cũ.
''')
    md('## Train trên CUDA và kiểm tra bản lưu PT / xuất ONNX')
    code('''REPORT = train(DATA_ROOT, OUT, start_from=START_FROM, epochs=EPOCHS,
    batch_size=BATCH_SIZE, learning_rate=LEARNING_RATE, camera_weight=CAMERA_WEIGHT,
    patience=PATIENCE, seed=SEED, workers=NUM_WORKERS, amp=AMP, require_gpu=True)
print('Checkpoint được chọn: epoch', REPORT['selected']['epoch'])
print('Trạng thái:', REPORT['status'])
print('PT ↔ ONNX:', json.loads((OUT/'parity.json').read_text()))
''')
    md('''## Kết quả validation và biểu đồ loss

F1 ảnh/recall này là **validation ảnh cũ**. Không phải recall sự kiện, không phải kết quả test camera mới. Các clip lỗi đã khóa không được đưa vào bundle hoặc chọn checkpoint. Hãy kiểm tra video mới ở cả gần/trung bình, cười/nói chuyện và góc camera trước khi dùng profile mới.
''')
    code('''for source, metrics in REPORT['serialized_validation'].items():
    print(source, 'samples=', metrics['samples'], 'F1=', round(metrics['macro_f1'],4),
          'recall@0.70=', round(metrics['yawn_recall_at_070_including_unknown'],4),
          'false-yawn@0.70=', round(metrics['false_yawn_at_070'],4))
plt.figure(figsize=(9,3))
plt.plot([t['epoch'] for t in REPORT['trials']], [t['loss'] for t in REPORT['trials']])
plt.xlabel('Epoch'); plt.ylabel('Train loss'); plt.grid(alpha=.2); plt.show()
''')
    md('''## Tải model về project Windows

Cell dưới tạo `yawn_kaggle_result.zip` trong Output. Tải ZIP, giải nén **vào thư mục `DA2/models`**, để có `models/yawn_kaggle_near_medium/runtime.yaml`. Model mắt/YuNet tham chiếu bộ hiện có trong project; không cần train lại chúng.

```powershell
& '.\\.venv\\Scripts\\python.exe' -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend onnx --display
```

PT/ONNX được tạo cho PC. Muốn dùng NPU Radxa cần chuyển RKNN trên Linux và đo riêng, chưa được nghiệm thu trong notebook này.
''')
    code('''import shutil
from IPython.display import FileLink, display
result_zip = shutil.make_archive('/kaggle/working/yawn_kaggle_result', 'zip',
    root_dir=OUT.parent, base_dir=OUT.name)
print(result_zip)
display(FileLink(result_zip))
''')
    return {'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
            'language_info':{'name':'python','version':'3.12'}},'cells':[
            {**c,'id':f'cell-{i:02d}'} for i,c in enumerate(cells)]}


def build():
    o = options(ROOT/'configs/yawn_near_medium_training.yaml')
    config = load_config(o['runtime_config'])
    checked_annotations(o)
    data = verify_prepared_dataset(o['dataset'], config, o['recipe'])
    if data['validation_mode'] != 'static_only' or data['active_distances'] != ['near','medium']:
        raise ValueError('this Kaggle bundle requires the explicit near/medium experimental scope')
    files = {}
    def binary(name, path): files[name] = Path(path).read_bytes()
    def js(name, value): files[name] = json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    portable = copy.deepcopy(data)
    portable.pop('sources')
    for index, row in enumerate(portable['records']):
        if not row['file']: raise ValueError('missing native crop')
        original = o['dataset']/row['file']
        row['file'] = f"native/{row['split']}/{row['label']}/{index:07d}.png"
        binary(row['file'],original)
    portable['sources'] = [{'name':Path(s['file']).name,'sha256':s['sha256']} for s in data['sources']]
    js('dataset.json',portable)
    manifest = read_manifest(config.manifest)
    js('base_manifest.json',manifest)
    runtime = asdict(config); runtime.pop('manifest'); runtime.pop('log_dir')
    js('runtime_settings.json',runtime)
    binary('checkpoints/usb_refined.pt',artifact_path(config.manifest,manifest['classifiers']['yawn']['artifacts']['torch']))
    binary('checkpoints/original_kaggle.pt',ROOT/'camera_classical/best_yawn.pt')
    binary('annotations.csv',o['annotations'])
    binary('augmentation_preview.jpg',o['dataset']/'augmentation_preview.jpg')
    binary('kaggle_yawn_training.py',ROOT/'tools/kaggle_yawn_training.py')
    for path in (ROOT/'driver_monitor').glob('*.py'):
        binary('support/driver_monitor/'+path.name,path)
    binary('support/support_tools/finetune_yawn_distance.py',ROOT/'tools/finetune_yawn_distance.py')
    files['support/support_tools/__init__.py'] = b''
    files['requirements-kaggle.txt'] = REQUIREMENTS.encode()
    files['README.txt'] = ('Private dataset for the accompanying yawn_near_medium_kaggle.ipynb.\n'
        'Native BGR PNG crops; keep aspect and use the notebook shared preprocessing.\n'
        '575 training images / 160 static validation images. No independent camera test.\n').encode()
    import hashlib
    js('bundle.json',{'schema_version':1,'kind':'driver_monitor_yawn_near_medium',
        'checksums':{name:hashlib.sha256(content).hexdigest() for name,content in files.items()},
        'checkpoints':{'usb_refined':'checkpoints/usb_refined.pt','original_kaggle':'checkpoints/original_kaggle.pt'},
        'counts':dict(Counter(f"{r['domain']}/{r['split']}/{r['label']}" for r in portable['records'])),
        'camera_validation_pending':True,'test_videos_included':False})
    destination = ROOT/'kaggle_upload'; destination.mkdir(exist_ok=True)
    archive = destination/'yawn_near_medium_dataset.zip'
    temporary = destination/'yawn_near_medium_dataset.tmp.zip'
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as stream:
        for name, contents in sorted(files.items()):
            stream.writestr('yawn_near_medium/'+name,contents)
    temporary.replace(archive)
    nb_path = ROOT/'notebooks/yawn_near_medium_kaggle.ipynb'
    json_save(nb_path,notebook())
    verification = {'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha256(archive),
        'files':len(files),'images':len(portable['records']),'notebook':str(nb_path),
        'counts':json.loads(files['bundle.json'])['counts'],'kaggle_gpu_execution_observed':False}
    json_save(destination/'bundle_verification.json',verification)
    print(json.dumps(verification,indent=2))


if __name__ == '__main__':
    build()
