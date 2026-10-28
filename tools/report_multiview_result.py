"""Generate a reproducible evaluation report from saved predictions, with no tuning."""
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import os
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from driver_monitor.multiview_learning import evaluate
    from driver_monitor.models import sha256
    models = ROOT / 'models/multiview_20261013'
    output = ROOT / 'reports/multiview_20261013'
    dataset_root = ROOT / 'kaggle_upload/multiview_20261013'
    data = json.loads((dataset_root / 'dataset.json').read_text(encoding='utf-8'))
    counts = json.loads((ROOT / 'data_collection/multiview_20261013/bundle_summary.json').read_text(encoding='utf-8'))
    state_path = ROOT / 'kaggle_upload/multiview_cloud/latest.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    pc = json.loads((output / 'pc_verification.json').read_text(encoding='utf-8'))
    summary = json.loads((models / 'summary.json').read_text(encoding='utf-8'))
    reports = {task: json.loads((models / f'{task}_evaluation.json').read_text(encoding='utf-8')) for task in ('eye', 'yawn')}
    key = 'camera/WIN_20261013_17_07_01_Pro/letterbox_640'
    tables, flat, per_eye = {}, [], {}
    labels = {'eye': ['Nhắm', 'Mở'], 'yawn': ['Không ngáp', 'Ngáp']}
    titles = {'eye': 'Model mắt', 'yawn': 'Model ngáp'}
    for task, report in reports.items():
        tables[task] = {}
        for version in ('baseline', 'candidate'):
            metrics = report['heldout_camera'][version]['groups'][key]
            selected = [row for row in report['heldout_predictions'] if row['resolution'] == 'letterbox_640']
            scores = np.asarray([row[version] for row in selected])
            truth = np.asarray([row['label'] == report['classes'][0 if task == 'eye' else 1] for row in selected])
            positive = scores[:, 0 if task == 'eye' else 1]
            pairwise = positive[truth, None] - positive[~truth][None, :]
            auc = float(np.mean((pairwise > 0) + .5 * (pairwise == 0))) if pairwise.size else None
            tables[task][version] = {**metrics, 'brier_score': float(np.mean((positive-truth)**2)), 'roc_auc': auc}
            for mode, measured in (('argmax', metrics), ('confidence_quality_proxy', metrics['confidence_and_quality_gate'])):
                for label, measured_class in measured['per_class'].items():
                    flat.append({'task':task,'version':version,'resolution':'letterbox_640','mode':mode,
                                 'class':label,**measured_class,'accuracy':measured['accuracy'],
                                 'macro_f1':measured['macro_f1'],'coverage':measured['coverage']})
        fig, axes = plt.subplots(2, 2, figsize=(10, 8.2))
        for column, version in enumerate(('baseline', 'candidate')):
            metric = tables[task][version]
            for row, mode in enumerate(('argmax', 'gate')):
                values = np.array(metric['confusion_matrix'] if mode=='argmax' else metric['confidence_and_quality_gate']['confusion_matrix_with_unknown'])
                names = labels[task] + ([] if mode=='argmax' else ['UNKNOWN'])
                ax = axes[row, column]
                ax.imshow(values, cmap='Blues', vmin=0, vmax=max(1, metric['samples']))
                ax.set_xticks(range(len(names)), names)
                ax.set_yticks(range(2), labels[task])
                ax.set_xlabel('Nhãn dự đoán'); ax.set_ylabel('Nhãn thực tế')
                heading = 'Trước fine-tune' if version=='baseline' else 'Sau fine-tune'
                ax.set_title(heading + (' · argmax' if mode=='argmax' else ' · confidence + chất lượng'))
                for (i, j), value in np.ndenumerate(values):
                    ax.text(j, i, str(value), ha='center', va='center', fontsize=17,
                            color='white' if value > metric['samples']*.5 else '#14252c')
        fig.suptitle(titles[task]+' · Clip test giữ riêng · Bản mô phỏng 640×480', fontsize=14)
        fig.text(.5,.013,'Các ô là số crop. Cột UNKNOWN vẫn nằm trong mẫu số; đây chưa phải đánh giá sự kiện theo thời gian.',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.035,1,.95)); fig.savefig(output/f'{task}_confusion_comparison.png',dpi=170); plt.close(fig)
        if task == 'eye':
            for index, anatomical_side in ((0,'left'),(1,'right')):
                for version in ('baseline','candidate'):
                    rows = [r for r in report['heldout_predictions'] if r['resolution']=='letterbox_640' and r['eye_index']==index]
                    rows = [{**r,'domain':'camera'} for r in rows]
                    metric = evaluate(rows,np.asarray([r[version] for r in rows]),'eye')
                    per_eye[f'{anatomical_side}/{version}'] = metric
    csv_path = output / 'metrics_640.csv'
    with csv_path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    # Keep a clean copy of the exported provenance; starting refinements are historical.
    manifest_path = models/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if 'refinement' in manifest:manifest['starting_model_refinement']=manifest.pop('refinement')
    if 'starting_model_export_versions' not in manifest:manifest['starting_model_export_versions']=manifest.get('export_versions',{})
    manifest['export_versions']={'torch':summary['torch'],'numpy':summary['numpy'],
                                 'onnx':summary['parity']['eye']['onnx_version'],
                                 'onnxruntime':summary['parity']['eye']['onnxruntime_version'],
                                 'ultralytics_declared_pin':'8.4.163'}
    provenance=manifest['multiview_refinement']
    bundle=json.loads((dataset_root/'bundle.json').read_text(encoding='utf-8'))
    provenance.update(selected_epochs={task:report['selected_epoch'] for task,report in reports.items()},
                      starting_checkpoint_sha256={task:sha256(dataset_root/path) for task,path in bundle['checkpoints'].items()},
                      method='Classify conv/BN affine/Linear; frozen backbone and BN buffers',
                      augmentation_at_inference=False,
                      promotion_status='experimental_only: heldout argmax unchanged; confident eye errors increased',
                      result_archive_sha256=state['cloud_result']['sha256'])
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pc.update(manifest_sha256=sha256(manifest_path),metadata_note='Export provenance clarified locally; PT and ONNX bytes unchanged from Kaggle.')
    (output/'pc_verification.json').write_text(json.dumps(pc,indent=2),encoding='utf-8')
    state.update(status='complete',selected_epochs=provenance['selected_epochs'],pc_parity_verified=True,
                 promotion_status='experimental_only',report=str(output/'README.md'))
    state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
    (output/'evaluation_640.json').write_text(json.dumps({'metrics':tables,'anatomical_per_eye':per_eye,
                'camera_live_acceptance':False,'subject_independence':False,'event_accuracy':None},indent=2),encoding='utf-8')
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,(task,report) in zip(axes,reports.items()):
        ax.plot([r['epoch'] for r in report['trials']],[r['loss'] for r in report['trials']],marker='.',color='#218578')
        ax.axvline(report['selected_epoch'],linestyle='--',color='#db8a25',label='Checkpoint chọn bằng validation')
        ax.set_title(titles[task]);ax.set_xlabel('Epoch');ax.set_ylabel('Cross entropy train');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(output/'training_loss.png',dpi=170);plt.close(fig)
    def pct(value):return f'{100*value:.2f}%'
    lines=['# Fine-tune mắt và ngáp nhiều góc — 13/10/2026','',
           '**Đã huấn luyện cả hai model trên Kaggle GPU Tesla T4. Chưa chứng minh cải thiện trên clip test giữ riêng; bản mới chỉ dùng thử nghiệm.**','',
           '## Dữ liệu và cách chia','',
           '- Video train: `WIN_20261013_17_05_46_Pro.mp4` (góc bên), `WIN_20261013_17_07_34_Pro.mp4` (camera thấp).',
           '- Video test nguyên clip: `WIN_20261013_17_07_01_Pro.mp4` (góc chéo). Không đưa frame của clip này vào loss, chọn epoch hoặc hiệu chỉnh ngưỡng.',
           '- Validation để chọn checkpoint: ảnh tĩnh giữ lại từ dữ liệu cũ; chưa có camera validation độc lập.',
           '- Ba clip cùng một người/buổi quay; đây là đánh giá phát triển, chưa phải kiểm thử theo người độc lập. Không gán cả đoạn thành mắt mở: nhãn từng mắt/ngáp được xem theo frame, bỏ trường hợp không rõ.',
           f'- Tổng **{counts["records"]:,} crop** (gồm train/val/test, hai tác vụ và dữ liệu cũ). Loại {counts["camera_unknown_labels_excluded"]} nhãn camera không chắc chắn.',
           '- Mỗi frame được chuẩn bị ở native 1920×1080 và bản giữ tỷ lệ 640×360, đệm thành 640×480. Hai bản cùng frame dùng cùng split và có tương quan; không cộng chúng thành mẫu độc lập.',
           '- Bản 640 mô phỏng giảm độ phân giải; chưa chứng minh tương đương pixel/FOV với camera USB đang mở trực tiếp ở 640×480. Video MP4 đã nén.',
           '', '| Tác vụ | Train | Validation | Test native | Test mô phỏng 640 |','|---|---:|---:|---:|---:|']
    for task in reports:
        subset=[r for r in data['records'] if r['task']==task]
        amount=lambda split,res=None:sum(r['split']==split and (res is None or r['resolution']==res) for r in subset)
        lines.append(f'| {titles[task]} | {amount("train")} | {amount("val")} | {amount("test","native_1080")} | {amount("test","letterbox_640")} |')
    lines += ['', '## Kết quả trên clip test — chỉ bản mô phỏng 640×480','',
              '| Model | Phiên bản | Accuracy | F1 macro | Brier (thấp hơn tốt hơn) | ROC-AUC | Crop |',
              '|---|---|---:|---:|---:|---:|---:|']
    for task in reports:
        for version,metric in tables[task].items():
            lines.append(f'| {titles[task]} | {version} | {pct(metric["accuracy"])} | {pct(metric["macro_f1"])} | {metric["brier_score"]:.6f} | {metric["roc_auc"]:.4f} | {metric["samples"]} |')
    lines += ['', '### Precision, recall và F1 của model mới','',
              '| Model | Lớp | Precision | Recall | F1 | Support |','|---|---|---:|---:|---:|---:|']
    for task in reports:
        for label,metric in tables[task]['candidate']['per_class'].items():
            lines.append(f'| {titles[task]} | {label} | {pct(metric["precision"])} | {pct(metric["recall"])} | {pct(metric["f1"])} | {metric["support"]} |')
    lines += ['', '### Ma trận nhầm lẫn','',
              'Hàng là nhãn thực tế, cột là nhãn dự đoán. Hàng trên dùng argmax; hàng dưới thêm confidence/chất lượng và giữ UNKNOWN trong mẫu số.','',
              '![Mắt trước và sau fine-tune](eye_confusion_comparison.png)','',
              '![Ngáp trước và sau fine-tune](yawn_confusion_comparison.png)','',
              'Mắt: cả trước/sau đều có 4 crop `Open → Closed`, không bỏ sót 16 crop `Closed` bằng argmax. Sau ngưỡng confidence 0,8, lỗi mắt mở bị khẳng định là nhắm tăng từ 3 lên 4; số UNKNOWN vẫn là 1/87. Vì vậy không chọn bản mới làm mặc định.',
              'Ngáp: 36 crop không ngáp và 8 crop ngáp đều đúng ở bản 640; kết quả mẫu nhỏ này không có nghĩa hệ thống đạt 100% trên camera thực hoặc mọi góc.',
              '', '### Dữ liệu UNKNOWN','',
              '| Model | Phiên bản | Coverage 640 | F1 macro có UNKNOWN | Coverage native 1080 |','|---|---|---:|---:|---:|']
    for task,report in reports.items():
        for version,metric in tables[task].items():
            gate=metric['confidence_and_quality_gate']
            native=report['heldout_camera'][version]['groups'][key.replace('letterbox_640','native_1080')]['confidence_and_quality_gate']
            lines.append(f'| {titles[task]} | {version} | {pct(gate["coverage"])} | {pct(gate["macro_f1"])} | {pct(native["coverage"])} |')
    lines += ['', 'Native có nhiều frame không qua cổng chất lượng ảnh. Bảng này là proxy theo crop tĩnh, chưa áp dụng xác nhận thời gian, EMA ngáp, motion gate khi chuyển đầu và logic hai mắt. Không coi coverage là recall sự kiện.',
              '', '## Huấn luyện và kiến trúc','',
              '- Fine-tune từ `eye_refined_v4` và `yawn_kaggle_near_medium`; không train từ đầu. Cả hai vẫn là YOLOv8n classification, input RGB 224×224. YuNet và logic thời gian không đổi.',
              '- Chỉ cập nhật khối Classify conv/BN affine/Linear; backbone và running buffers BN được đối chiếu và giữ nguyên.',
              '- AdamW, learning rate 0,0001; weight decay 0,0001; batch 64; seed 42; tối đa 30 epoch; patience 7. Sampling camera/static 60/40 và cân bằng lớp, nên loss train là loss theo sampler, không phải phân bố camera tự nhiên.',
              '- Augmentation trên crop gốc: dịch ±2 pixel (60%), downsample ×0,5/×0,75 (40%, chỉ khi cạnh nhỏ ≥36 px), Gaussian σ0,35–0,65 (20%), motion blur ngang dài 3 (10%), gamma 0,8–1,2 (60%), lật ngang (50%), grayscale (15%).',
              '- Không augmentation validation/test/runtime. Sau augmentation dùng cùng PIL resize bilinear, center crop, RGB/255 như runtime. Không giảm ngưỡng quality/confidence để làm đẹp kết quả.',
              '- Chọn checkpoint bằng F1/Brier validation tĩnh, có chặn suy giảm F1 nhóm >2,5 điểm phần trăm hoặc recall có confidence >5 điểm. Model mắt các epoch sau bị chặn do giảm recall mắt mở trên ảnh ROI validation.',
              '', '| Model | Tổng tham số | Tham số fine-tune | Epoch đã chạy | Epoch chọn |','|---|---:|---:|---:|---:|']
    for task,report in reports.items():
        lines.append(f'| {titles[task]} | {pc["tasks"][task]["parameter_count"]:,} | {report["trainable_parameters"]:,} | {len(report["trials"])} | {report["selected_epoch"]} |')
    lines += ['', '![Loss huấn luyện](training_loss.png)','',
              f'- GPU: {summary["GPU"]}; Torch {summary["torch"]}; NumPy {summary["numpy"]}; Python {summary["python"].split()[0]}.',
              '- Head model: Conv → pooling → Linear 2 lớp → softmax. Thứ tự mắt `Closed, Open`; ngáp `no_yawn, yawn`. Manifest chứa checksum và preprocessing.',
              '', '## Kiểm tra xuất model và PC','',
              '| Model | Crop kiểm tra PT/ONNX PC | Delta xác suất lớn nhất | Nhãn lệch |','|---|---:|---:|---:|']
    for task in reports:
        value=pc['tasks'][task]
        lines.append(f'| {titles[task]} | {value["parity_samples"]} | {value["max_probability_delta"]:.3e} | {value["label_mismatches"]} |')
    lines += ['', f'- PC: Torch {pc["torch"]}, ONNX Runtime {pc["onnxruntime"]}. ONNX IR 7, opset 12; kiểm tra cả nhãn và ma trận trên crop test khớp kết quả GPU.',
              '- Smoke test runtime đầy đủ: 20 frame của video test, không lỗi. Đây là kiểm tra tích hợp, không đo FPS nghiệm thu.',
              '- Chưa kiểm thử camera live với checkpoint mới; chưa đo recall sự kiện, báo nhầm/giờ, độ trễ còi hoặc NPU Radxa.',
              '', '## Chạy thử bản mới','', 'Đóng ứng dụng Camera của Windows trước. Camera rời đã được xác định ở source 1; nếu thứ tự thiết bị thay đổi, probe lại.','',
              '```powershell', "Set-Location -LiteralPath 'C:\\Users\\P1 Gen 5\\Downloads\\DA2'",
              "& '.\\.venv\\Scripts\\python.exe' -m driver_monitor run --config models/multiview_20261013/runtime.yaml --source 1 --backend onnx --display", '```','',
              'Quay lại model đang dùng: thay `--config` bằng `models/yawn_kaggle_near_medium/runtime.yaml`. Cấu hình model gốc vẫn giữ nguyên.','',
              '## Tệp bàn giao và tái lập','',
              '- [Metric CSV](metrics_640.csv), [metric JSON và tách theo mắt của tài xế](evaluation_640.json), [kiểm tra PC](pc_verification.json).',
              '- [Model và manifest](../../models/multiview_20261013/manifest.json), [cấu hình thử nghiệm](../../models/multiview_20261013/runtime.yaml).',
              '- [Dataset ZIP](../../kaggle_upload/multiview_20261013.zip), [notebook](../../notebooks/driver_multiview_gpu.ipynb), [nhãn camera](../../data_collection/multiview_20261013/annotations.csv).',
              f'- [Notebook Kaggle Private](https://www.kaggle.com/code/{state["notebook_id"]}), [Dataset Kaggle Private](https://www.kaggle.com/datasets/{state["dataset_id"]}). Chỉ tài khoản sở hữu có quyền xem.',
              f'- SHA256 dataset ZIP: `{counts["sha256"]}`.',
              f'- SHA256 output ZIP gốc Kaggle: `{state["cloud_result"]["sha256"]}`. Metadata manifest được làm rõ tại PC; trọng số PT/ONNX giữ nguyên byte từ Kaggle.',
              '- GPU notebook v1 và ZIP dataset là bản bất biến đã chạy. Mã exporter hiện tại bổ sung metadata phiên bản và lịch sử trọng số cho các lần chạy tiếp theo.','',
              '## Cải thiện cần có thêm dữ liệu','',
              'Thu clip camera validation riêng và test từ người/buổi quay khác ở góc chính diện, chéo, thấp và gần–trung bình–xa; mỗi góc có mở, nhắm, nháy riêng, ngáp, cười và nói chuyện. Giữ các đoạn chuyển tiếp khó làm UNKNOWN khi không đủ nhãn. Sau đó có thể mở thêm tầng backbone để fine-tune, nhưng phải chọn bằng validation mới và kiểm thử cuối bằng clip chưa dùng; không điều chỉnh mô hình theo clip test hiện tại.','']
    (output/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'report':str(output/'README.md'),'promotion_status':state['promotion_status'],
                      'matrices':['eye_confusion_comparison.png','yawn_confusion_comparison.png']},ensure_ascii=False))


if __name__=='__main__':
    main()
