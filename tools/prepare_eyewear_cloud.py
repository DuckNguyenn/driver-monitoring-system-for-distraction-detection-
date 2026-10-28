"""Attach public CelebA directly; upload code and YuNet only, never CelebA pixels."""
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import json
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from driver_monitor.config import load_config
from driver_monitor.models import artifact_path,read_manifest
from tools.build_yawn_kaggle_bundle import REQUIREMENTS


def main():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S');folder=ROOT/'kaggle_upload/eyewear_cloud'/stamp
    data=folder/'dataset';notebook=folder/'notebook';data.mkdir(parents=True);notebook.mkdir()
    shutil.copytree(ROOT/'driver_monitor',data/'support/driver_monitor',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT/'tools/kaggle_eyewear_training.py',data/'kaggle_eyewear_training.py')
    config=load_config(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml');manifest=read_manifest(config.manifest)
    detector=artifact_path(config.manifest,manifest['detector']);shutil.copy2(detector,data/detector.name)
    manifest['detector']['file']=detector.name
    (data/'runtime_manifest.json').write_text(json.dumps(manifest,indent=2))
    (data/'crop_config.json').write_text(json.dumps(asdict(config),default=str,indent=2))
    dataset_id='nguyntrnminhc/driver-eyewear-code-'+stamp;kernel_id='nguyntrnminhc/driver-eyewear-gpu-'+stamp
    (data/'dataset-metadata.json').write_text(json.dumps({'id':dataset_id,'title':'Driver Eyewear Code '+stamp,
       'licenses':[{'name':'other'}],'description':'Private code and OpenCV YuNet only. No CelebA images. Public CelebA input is attached directly to research notebook.'},indent=2))
    cells=[]
    def cell(kind,source):
        value={'cell_type':kind,'id':'eyewear-'+str(len(cells)),'metadata':{},'source':source.splitlines(True)}
        if kind=='code':value.update(execution_count=None,outputs=[])
        cells.append(value)
    cell('markdown','# HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ\n\nBộ nhận diện kính RGB độc lập: MobileNetV3-Small. Không sửa model mắt gốc hay ngáp. CelebA gắn trực tiếp làm input, không xuất lại ảnh. YuNet và crop mặt theo runtime; preprocessing 128×128 được ghi trong manifest. Chọn epoch/ngưỡng bằng validation; test chỉ đo sau khi khóa. Chưa nghiệm thu trên camera USB với kính cận. Nguồn: https://mmlab.ie.cuhk.edu.hk/projects/CelebA.html\n')
    cell('code',"""import sys,subprocess
from pathlib import Path
from importlib.metadata import version
requirements=Path('/kaggle/working/requirements.txt');requirements.write_text(__REQUIREMENTS__)
constraints=Path('/kaggle/working/gpu-constraints.txt');constraints.write_text(''.join(f'{n}=={version(n)}\\n' for n in ('torch','torchvision')))
subprocess.check_call([sys.executable,'-m','pip','install','--quiet','--only-binary=:all:','-c',str(constraints),'-r',str(requirements)])
""".replace('__REQUIREMENTS__',repr(REQUIREMENTS)))
    cell('code',"""script=next(Path('/kaggle/input').rglob('kaggle_eyewear_training.py'))
subprocess.check_call([sys.executable,'-u',str(script),'--root',str(script.parent),'--output','/kaggle/working/eyewear_model','--epochs','10'])
""")
    cell('code',"import json\nreport=json.loads(Path('/kaggle/working/eyewear_model/evaluation.json').read_text())\nprint(report['status'],report.get('test_gate'))\n")
    filename='eyewear_selector_gpu.ipynb';content=json.dumps({'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','language':'python','display_name':'Python 3'}},'cells':cells},ensure_ascii=False,indent=2)
    (notebook/filename).write_text(content,encoding='utf-8');(ROOT/'notebooks'/filename).write_text(content,encoding='utf-8')
    (notebook/'kernel-metadata.json').write_text(json.dumps({'id':kernel_id,'title':'Driver Eyewear GPU '+stamp,'code_file':filename,
        'language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':True,'machine_shape':'NvidiaTeslaT4',
        'dataset_sources':[dataset_id,'jessicali9530/celeba-dataset'],'competition_sources':[],'kernel_sources':[],'model_sources':[]},indent=2))
    state={'dataset_id':dataset_id,'notebook_id':kernel_id,'dataset_dir':str(data),'notebook_dir':str(notebook),'status':'prepared'}
    (folder.parent/'latest.json').write_text(json.dumps(state,indent=2));print(json.dumps(state,indent=2))


if __name__=='__main__':main()
