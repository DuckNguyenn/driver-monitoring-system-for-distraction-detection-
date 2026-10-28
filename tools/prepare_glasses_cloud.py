"""Prepare a Private Kaggle job for the locked glasses adaptation bundle."""
from pathlib import Path
from datetime import datetime,timezone
import json
import shutil
import sys
import argparse
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from driver_monitor.models import sha256
from tools.build_yawn_kaggle_bundle import REQUIREMENTS


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ROOT/'kaggle_upload/glasses_adaptation_20261013.zip')
    args=parser.parse_args(argv)
    archive=args.archive.resolve()
    with zipfile.ZipFile(archive) as zipped:
        locked=json.loads(zipped.read('bundle.json'))
        metadata=json.loads(zipped.read('dataset.json'))
    if locked['kind']!='driver_monitor_glasses_adaptation':raise ValueError('Incorrect training bundle')
    has_rgb=bool(metadata.get('new_rgb_glasses_camera_present'))
    run_id=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    folder=ROOT/'kaggle_upload/glasses_cloud'/run_id
    dataset_dir=folder/'dataset';notebook_dir=folder/'notebook'
    dataset_dir.mkdir(parents=True);notebook_dir.mkdir()
    shutil.copy2(archive,dataset_dir/archive.name)
    dataset_id='nguyntrnminhc/driver-eye-glasses-'+run_id
    notebook_id='nguyntrnminhc/driver-eye-glasses-gpu-'+run_id
    cells=[]
    def cell(kind,source):
        value={'cell_type':kind,'id':f'glasses-{len(cells):02d}','metadata':{},'source':source.splitlines(True)}
        if kind=='code':value.update(execution_count=None,outputs=[])
        cells.append(value)
    cell('markdown','''# HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ

## Fine tune model mắt khi đeo kính

Chạy GPU, fine-tune C2f cuối và Classify từ checkpoint mắt đã khóa trong bundle. MRL có split theo người cho giai đoạn fine-tune này; dữ liệu RGB cũ giữ nguyên các split để kiểm tra hồi quy. Không dùng test để chọn epoch. Chưa chứng minh MRL độc lập với dữ liệu train checkpoint gốc, và audit trước đó đã xem một phần MRL. Các phép đo là phát triển, không phải nghiệm thu video RGB người mới/camera USB/Radxa.

Sampling: RGB rehearsal 55%, MRL kính 30%, MRL không kính 15%, cân bằng lớp. Validation chặn suy giảm RGB/không kính; cần tăng F1 kính ít nhất 3 điểm. Giữ nguyên preprocessing và ngưỡng runtime. Nếu không checkpoint nào đạt, chỉ xuất báo cáo và không thay model. Hiện chưa có video RGB đeo kính của người dùng.
''')
    if has_rgb:
        cells[0]['source']=''.join(cells[0]['source']).replace(
            'Sampling: RGB rehearsal 55%, MRL kính 30%, MRL không kính 15%, cân bằng lớp. Validation chặn suy giảm RGB/không kính; cần tăng F1 kính ít nhất 3 điểm.',
            'Sampling và tiêu chí validation RGB kính được ghi ở cell tiếp theo.').replace(
            'Hiện chưa có video RGB đeo kính của người dùng.','Gói này có crop RGB kính đã xem và gán nhãn thủ công; chưa có nghiệm thu cảnh báo theo video.').splitlines(True)
        cell('markdown','''## Gói RGB kính đã duyệt

Gói này có video RGB đeo kính đã gán nhãn thủ công. Train/validation/test của phần RGB mới tách theo người và buổi thu; test không dùng để chọn epoch. Sampling: RGB kính45%, RGB hồi quy25%, MRL kính20%, MRL không kính10%, cân bằng Open/Closed trong từng nhóm.

Model chỉ đủ điều kiện nếu F1 validation RGB kính tăng ít nhất2 điểm, không tăng mắt mở bị khẳng định nhắm, không giảm recall nhắm có confidence, và giữ các kiểm tra hồi quy. Xuất riêng ma trận RGB kính. Accuracy ảnh không thay thế blink hoặc cảnh báo theo thời gian. Không tự thay model mắt gốc hoặc ngáp, không tự bật candidate mới trong runtime.
''')
    cell('code','''import sys,subprocess,os,json
from pathlib import Path
from importlib.metadata import version
assert (3,9)<=sys.version_info[:2]<(3,14)
os.environ['YOLO_CONFIG_DIR']='/kaggle/working/.config/ultralytics'
os.environ['MPLCONFIGDIR']='/kaggle/working/.config/matplotlib'
requirements=Path('/kaggle/working/requirements-glasses.txt')
requirements.write_text(__REQUIREMENTS__,encoding='utf-8')
constraints=Path('/kaggle/working/constraints-gpu.txt')
constraints.write_text(''.join(f'{name}=={version(name)}\\n' for name in ('torch','torchvision')),encoding='utf-8')
subprocess.check_call([sys.executable,'-m','pip','install','--quiet','--only-binary=:all:','-c',str(constraints),'-r',str(requirements)])
'''.replace('__REQUIREMENTS__',repr(REQUIREMENTS)))
    cell('code','''matches=[path for path in Path('/kaggle/input').rglob('bundle.json') if json.loads(path.read_text()).get('kind')=='driver_monitor_glasses_adaptation']
assert len(matches)==1
bundle_root=matches[0].parent
subprocess.check_call([sys.executable,'-u',str(bundle_root/'kaggle_glasses_training.py'),
                      '--root',str(bundle_root),'--output','/kaggle/working/glasses_model','--epochs','24','--patience','7'])
''')
    cell('code','''report=json.loads(Path('/kaggle/working/glasses_model/evaluation.json').read_text())
print('Status:',report['status'],'selected epoch:',report['selected_epoch'])
if 'test' in report:
    for version_name,groups in report['test'].items():
        for name,metric in groups.items():
            print(version_name,name,'F1:',metric['macro_f1'],'accuracy:',metric['accuracy'])
    from IPython.display import display,Image
    for file in Path('/kaggle/working/glasses_model').glob('*mrl_glasses_matrix.png'):
        display(Image(filename=str(file)))
print('Download /kaggle/working/glasses_result.zip')
''')
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells}
    filename='eye_glasses_gpu.ipynb'
    (notebook_dir/filename).write_text(json.dumps(notebook,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'notebooks'/filename).write_text(json.dumps(notebook,ensure_ascii=False,indent=2),encoding='utf-8')
    dataset={'id':dataset_id,'title':'Driver Eye Glasses '+run_id,'licenses':[{'name':'other'}],
             'description':'Private research adaptation. MRL infrared eye crops with glasses metadata, subject-disjoint fine-tuning stage split and existing RGB rehearsal. Original training membership unknown. Not for public redistribution. RGB glasses camera acceptance pending.'}
    kernel={'id':notebook_id,'title':'Driver Eye Glasses GPU '+run_id,'code_file':filename,'language':'python','kernel_type':'notebook',
            'is_private':True,'enable_gpu':True,'enable_internet':True,'machine_shape':'NvidiaTeslaT4','dataset_sources':[dataset_id],
            'competition_sources':[],'kernel_sources':[],'model_sources':[]}
    (dataset_dir/'dataset-metadata.json').write_text(json.dumps(dataset,indent=2),encoding='utf-8')
    (notebook_dir/'kernel-metadata.json').write_text(json.dumps(kernel,indent=2),encoding='utf-8')
    state={'dataset_id':dataset_id,'notebook_id':notebook_id,'dataset_dir':str(dataset_dir),'notebook_dir':str(notebook_dir),
           'run_id':run_id,'archive_sha256':sha256(archive),'private':True,'status':'prepared'}
    state.update(new_rgb_glasses_camera_present=has_rgb)
    (folder/'setup.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    (folder.parent/'latest-prepared.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    print(json.dumps(state,indent=2))


if __name__=='__main__':main()
