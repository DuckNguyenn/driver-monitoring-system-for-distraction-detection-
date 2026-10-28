"""Prepare a Private Kaggle notebook that trains in a fresh Python process."""
from pathlib import Path
from datetime import datetime,timezone
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from driver_monitor.models import sha256
from tools.build_yawn_kaggle_bundle import REQUIREMENTS


def main():
    run_id=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    root=ROOT/'kaggle_upload/multiview_cloud'/run_id
    dataset_dir=root/'dataset';notebook_dir=root/'notebook'
    dataset_dir.mkdir(parents=True);notebook_dir.mkdir()
    archive=ROOT/'kaggle_upload/multiview_20261013.zip'
    shutil.copy2(archive,dataset_dir/archive.name)
    title='Driver Multiview '+run_id
    dataset_id='nguyntrnminhc/'+title.lower().replace(' ','-')
    notebook_title='Driver Multiview GPU '+run_id
    notebook_id='nguyntrnminhc/'+notebook_title.lower().replace(' ','-')
    cells=[]
    def md(value):cells.append({'cell_type':'markdown','metadata':{},'source':value.splitlines(True)})
    def code(value):cells.append({'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':value.splitlines(True)})
    md('''# Fine-tune mắt và ngáp nhiều góc trên Kaggle GPU

Gói chứa crop camera từ hai clip train; clip **WIN_20261013_17_07_01_Pro** chỉ dùng cho test sau khi chọn checkpoint. Validation là dữ liệu ảnh cũ, không dùng frame test để chọn epoch/ngưỡng. Cùng một người/buổi quay, chưa phải kiểm thử độc lập theo người.

Model bắt đầu từ eye_refined_v4 và yawn_kaggle_near_medium. Fine-tune Classify conv/BN affine/linear, backbone/BN running buffers cố định. Augmentation dịch crop, độ sáng, downsampling và blur nhẹ trước cùng preprocessing 224×224. Frame mắt khó đọc loại khỏi train. Hai độ phân giải từ cùng frame kế thừa một split và không được coi là hai mẫu độc lập.

GPU được yêu cầu; notebook dừng nếu không có CUDA. Huấn luyện chạy trong **Python process mới** sau khi cài dependency để tránh kernel giữ NumPy phiên bản cũ trong bộ nhớ. Output gồm model PT/ONNX, manifest, thống kê trước/sau, confusion matrix và UNKNOWN theo confidence/chất lượng. Các ngưỡng runtime giữ nguyên; chưa có nghiệm thu camera trực tiếp/NPU.
''')
    code('''import sys, subprocess, os
from pathlib import Path
from importlib.metadata import version
assert (3,9) <= sys.version_info[:2] < (3,14), 'Verify binary wheels for this Python version.'
os.environ['YOLO_CONFIG_DIR']='/kaggle/working/.config/ultralytics'
os.environ['MPLCONFIGDIR']='/kaggle/working/.config/matplotlib'
requirements=Path('/kaggle/working/requirements-multiview.txt')
requirements.write_text(__REQUIREMENTS__,encoding='utf-8')
constraints=Path('/kaggle/working/gpu-constraints.txt')
constraints.write_text(''.join(f'{name}=={version(name)}\\n' for name in ('torch','torchvision')),encoding='utf-8')
subprocess.check_call([sys.executable,'-m','pip','install','--quiet','--only-binary=:all:','-c',str(constraints),'-r',str(requirements)])
'''.replace('__REQUIREMENTS__',repr(REQUIREMENTS)))
    code('''import json
matches=[path for path in Path('/kaggle/input').rglob('bundle.json') if json.loads(path.read_text()).get('kind')=='driver_monitor_multiview']
assert len(matches)==1, 'Attach exactly one multiview dataset.'
bundle_root=matches[0].parent
print('Dataset:',bundle_root)
subprocess.check_call([sys.executable,'-u',str(bundle_root/'kaggle_multiview_training.py'),
                      '--root',str(bundle_root),'--output','/kaggle/working/multiview_model',
                      '--epochs','30','--batch-size','64','--patience','7'])
''')
    code('''summary=json.loads(Path('/kaggle/working/multiview_model/summary.json').read_text())
print(json.dumps(summary,indent=2))
from IPython.display import display,Image
for path in sorted(Path('/kaggle/working/multiview_model').glob('*letterbox_640_matrix.png')):
    print(path.name)
    display(Image(filename=str(path)))
print('Download /kaggle/working/multiview_result.zip')
''')
    for index,cell in enumerate(cells):cell['id']=f'multiview-{index:02d}'
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells}
    file='driver_multiview_gpu.ipynb'
    (notebook_dir/file).write_text(json.dumps(notebook,indent=2,ensure_ascii=False),encoding='utf-8')
    (ROOT/'notebooks'/file).write_text(json.dumps(notebook,indent=2,ensure_ascii=False),encoding='utf-8')
    dataset={'id':dataset_id,'title':title,'licenses':[{'name':'other'}],
             'description':'Private research crops for this user. Eye/yawn multi-view GPU refinement. Two camera clips train, one whole clip held out, retained static validation. One person/session; no independent live-camera acceptance claim. Source rights retained; not for public redistribution.'}
    metadata={'id':notebook_id,'title':notebook_title,'code_file':file,'language':'python','kernel_type':'notebook',
              'is_private':True,'enable_gpu':True,'enable_internet':True,'machine_shape':'NvidiaTeslaT4',
              'dataset_sources':[dataset_id],'competition_sources':[],'kernel_sources':[],'model_sources':[]}
    (dataset_dir/'dataset-metadata.json').write_text(json.dumps(dataset,indent=2),encoding='utf-8')
    (notebook_dir/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    setup={'dataset_id':dataset_id,'notebook_id':notebook_id,'dataset_dir':str(dataset_dir),
           'notebook_dir':str(notebook_dir),'run_id':run_id,'dataset_sha256':sha256(archive),
           'private':True,'status':'prepared','gpu_execution_observed':False}
    (root/'setup.json').write_text(json.dumps(setup,indent=2),encoding='utf-8')
    (root.parent/'latest.json').write_text(json.dumps(setup,indent=2),encoding='utf-8')
    print(json.dumps(setup,indent=2))


if __name__=='__main__':main()
