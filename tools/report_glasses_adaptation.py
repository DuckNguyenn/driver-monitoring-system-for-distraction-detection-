"""Report the actual glasses adaptation results and remaining camera evidence."""
from pathlib import Path
import csv
import json
import os
ROOT=Path(__file__).resolve().parents[1]
TITLE='HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ'


def main():
    import numpy as np
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=ROOT/'models/eye_glasses_adapted';out=ROOT/'reports/glasses_adaptation_20261013'
    report=json.loads((folder/'evaluation.json').read_text(encoding='utf-8'))
    pc=json.loads((out/'pc_verification.json').read_text(encoding='utf-8'))
    bundle=json.loads((out/'bundle.json').read_text(encoding='utf-8'))
    state=json.loads((ROOT/'kaggle_upload/glasses_cloud/latest.json').read_text(encoding='utf-8'))
    def pct(n):return f'{100*n:.2f}%'
    names={'mrl_glasses':'MRL có kính','mrl_no_glasses':'MRL không kính','rgb_rehearsal':'RGB hồi quy cũ'}
    metrics=[]
    for group,title in names.items():
        fig,axes=plt.subplots(2,2,figsize=(10,8))
        for column,version in enumerate(('baseline','candidate')):
            measured=report['test'][version][group]
            for row,mode in enumerate(('argmax','confidence')):
                value=measured if row==0 else measured['confidence_and_quality_gate']
                matrix=np.asarray(value['confusion_matrix'] if row==0 else value['confusion_matrix_with_unknown'])
                ax=axes[row,column];ax.imshow(matrix,cmap='Blues',vmin=0,vmax=max(1,measured['samples']/2))
                labels=['Nhắm','Mở']+(['UNKNOWN'] if row else [])
                ax.set_xticks(range(len(labels)),labels);ax.set_yticks(range(2),['Nhắm','Mở'])
                ax.set_title(('Trước' if column==0 else 'Sau')+(' · argmax' if row==0 else ' · confidence ≥0,8'))
                ax.set_xlabel('Nhãn dự đoán');ax.set_ylabel('Nhãn thực tế')
                for (i,j),n in np.ndenumerate(matrix):ax.text(j,i,str(n),ha='center',va='center',fontsize=16,color='white' if n>measured['samples']*.3 else '#153139')
                for label,score in value['per_class'].items():
                    metrics.append({'group':group,'version':version,'mode':mode,'class':label,**score,
                                    'accuracy':value['accuracy'],'macro_f1':value['macro_f1'],'coverage':value['coverage']})
        fig.suptitle(title+' · Test của giai đoạn fine-tune kính',fontsize=15)
        fig.tight_layout(rect=(0,0,1,.95));fig.savefig(out/f'{group}_comparison.png',dpi=165);plt.close(fig)
    with (out/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(metrics[0]));writer.writeheader();writer.writerows(metrics)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    trials=report['trials'];epochs=[t['epoch'] for t in trials]
    axes[0].plot(epochs,[t['loss'] for t in trials],marker='.',color='#268575')
    axes[0].set_xlabel('Epoch');axes[0].set_ylabel('Cross entropy train');axes[0].set_title('Loss theo sampler')
    for group,color in (('rgb_rehearsal','#268575'),('mrl_glasses','#e19525'),('mrl_no_glasses','#608caf')):
        axes[1].plot(epochs,[t['validation'][group]['macro_f1'] for t in trials],label=names[group],color=color)
    axes[1].set_xlabel('Epoch');axes[1].set_ylabel('F1 macro validation');axes[1].legend(fontsize=8)
    for ax in axes:ax.axvline(report['selected_epoch'],color='#555',linestyle='--');ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'training_curves.png',dpi=165);plt.close(fig)
    lines=['# '+TITLE,'','## Nâng cấp model mắt khi đeo kính','',
           '**Đã fine-tune và có cải thiện trên MRL hồng ngoại. Độ chính xác khi người dùng đeo kính cận trước camera USB còn thiếu video RGB để kiểm chứng. Model mới giữ ở profile thử nghiệm.**','',
           '### Kết quả trước và sau trên cùng tập test của giai đoạn này','',
           '| Nhóm | Ảnh | Accuracy trước → sau | F1 macro trước → sau | Recall mắt nhắm trước → sau |','|---|---:|---:|---:|---:|']
    for group,title in names.items():
        a=report['test']['baseline'][group];b=report['test']['candidate'][group]
        lines.append(f'| {title} | {a["samples"]} | {pct(a["accuracy"])} → {pct(b["accuracy"])} | {pct(a["macro_f1"])} → {pct(b["macro_f1"])} | {pct(a["per_class"]["Closed"]["recall"])} → {pct(b["per_class"]["Closed"]["recall"])} |')
    lines += ['', 'Ảnh RGB hồi quy gồm hai bản độ phân giải của cùng frame từ một clip đã kiểm tra trong phát triển; không coi 174 crop là 174 mẫu độc lập. Chưa có ảnh RGB đeo kính mới của người dùng trong bộ này.',
              'Mẫu test mới khác mẫu audit 1.024 ảnh ở báo cáo trước. Các số trước–sau trong bảng đều được đo trên cùng mẫu của lần fine-tune này.',
              '', '### Ma trận nhóm đeo kính','', '![MRL kính trước sau](mrl_glasses_comparison.png)','',
              'Hàng là nhãn thực tế, cột là nhãn dự đoán. Hàng dưới giữ confidence 0,8 và có cột UNKNOWN. Cổng chất lượng camera không áp dụng cho ảnh MRL đã cắt sẵn.',
              '', 'Mắt nhắm nhận thành mở giảm từ 74 xuống 29/256 ảnh bằng argmax. Mắt mở nhận thành nhắm tăng từ 29 lên 41/256; đây là đánh đổi phải kiểm tra trên video trước khi dùng làm cảnh báo.',
              'Ở confidence 0,8, mắt nhắm bị khẳng định là mở giảm từ 61 xuống 8, nhưng UNKNOWN tăng từ 46 lên 84/512. Mắt mở bị khẳng định là nhắm là 18 trước và 19 sau. Vì vậy accuracy ảnh tăng chưa đồng nghĩa số báo nhầm/giờ giảm.',
              '', '### Chất lượng ở confidence vận hành','',
              '| Nhóm | Coverage trước → sau | Recall Closed có confidence trước → sau |','|---|---:|---:|']
    for group,title in names.items():
        a=report['test']['baseline'][group]['confidence_and_quality_gate'];b=report['test']['candidate'][group]['confidence_and_quality_gate']
        lines.append(f'| {title} | {pct(a["coverage"])} → {pct(b["coverage"])} | {pct(a["per_class"]["Closed"]["recall"])} → {pct(b["per_class"]["Closed"]["recall"])} |')
    lines += ['', '### Kiến trúc và huấn luyện','',
              '- Giữ YOLOv8n classification, đầu vào RGB224; bắt đầu từ `eye_refined_v4`. Tổng kiến trúc không đổi; mở tầng C2f cuối (8) và Classify (9), các tầng trước và BN running buffers giữ nguyên.',
              f'- {report["trainable_parameters"]:,} tham số được fine-tune. AdamW, LR C2f 0,00001 / Classify 0,00005, weight decay 0,0001; batch64; seed42; clip gradient1; tối đa24epoch, patience7.',
              f'- GPU {report["GPU"]}; chạy {len(trials)} epoch, chọn epoch {report["selected_epoch"]} bằng validation, không dùng test để chọn.',
              '- Tỷ trọng sampling RGB rehearsal55%, MRL kính30%, MRL không kính15%; mỗi nhóm cân bằng Open/Closed. Không để dữ liệu hồng ngoại thay hết dữ liệu RGB.',
              '- Augmentation nhẹ trước preprocessing runtime: dịch crop ±2px, gamma0,8–1,2, contrast0,85–1,15, lật ngang, grayscale, Gaussian/motion blur nhẹ và downsampling khi crop đủ lớn. Không augmentation val/test/runtime; không vẽ kính giả che mắt để tự tạo nhãn.',
              '- Giữ nguyên ngưỡng mắt0,8 và nhắm hai mắt1,5giây; ngưỡng chất lượng, YuNet và model ngáp giữ nguyên.',
              '', '![Training curves](training_curves.png)','',
              '### Dữ liệu và tính độc lập','',
              f'- Gói có {bundle["records"]:,} crop; [metadata và số lượng](bundle.json).',
              '- MRL val: s0002, s0014; MRL test: s0019, s0036; 33 người còn lại train. Mọi ảnh của một người thuộc cùng split trong giai đoạn fine-tune này.',
              '- Split Kaggle gốc thiếu kính–Closed trong test, nên tạo split mới bằng subject thay vì kế thừa thư mục gốc. [MRL chính thức](https://mrl.cs.vsb.cz/eyedataset.html) mô tả nhãn kính, trạng thái mắt và nguồn hồng ngoại.',
              '- Chưa xác định MRL có nằm trong dữ liệu train checkpoint gốc không; audit trước đã xem một phần MRL. Vì vậy chưa chứng minh đây là người/ảnh hoàn toàn mới đối với toàn bộ lịch sử của model.',
              '- RGB cũ giữ split đã lưu, dùng để chống hồi quy; chưa có split RGB đeo kính độc lập. Test theo người của toàn hệ thống, blink/ngáp tự nhiên, FAR/giờ và Radxa còn chưa nghiệm thu.',
              '', '### Kiểm tra PC','',
              f'- Torch {pc["torch"]}; ONNX Runtime {pc["onnxruntime"]}. {pc["parity_samples"]} crop đối chiếu, sai lệch xác suất tối đa {pc["max_probability_delta"]:.3e}, nhãn lệch {pc["label_mismatches"]}.',
              '- Ma trận và cột UNKNOWN trên PC khớp GPU. Chạy runtime 20 frame video cũ không lỗi; model/ngưỡng đang dùng được kiểm tra không bị thay.',
              '- Đây là kiểm tra tích hợp và inference; chưa phải tốc độ/accuracy nghiệm thu camera live.',
              '', '### Chuyển model mắt tự động theo kính','',
              'Bộ nhận diện kính RGB độc lập chọn giữa model mắt gốc và model mắt chuyên kính. YuNet, crop, ngưỡng thời gian và model ngáp được lấy nguyên từ cấu hình nền đang chọn. Không chuyển cả manifest hệ thống sang manifest ứng viên vì có thể làm thay đổi nhánh ngáp của profile khác.',
              'Chỉ chọn nhánh kính khi xác suất vượt ngưỡng validation và liên tục đủ 1,5 giây với các điểm đo mới. Đo kính tối đa 2 lần/giây. Điểm đo cũ hơn 0,8 giây, confidence không chắc, mất quan sát, đổi tài xế hoặc gap >250 ms trả về nhánh mắt gốc. Lỗi bộ chọn được ghi log và trả về mắt gốc.',
              'Một frame đổi nhánh được đánh dấu `eye_model_changed`: ngắt xác nhận mắt để không nối trạng thái hai model thành blink hoặc nhắm kéo dài. EMA và đợt ngáp giữ nguyên. Overlay trên PC/web/app ghi `eye:original` hoặc `eye:glasses`, không thêm nhãn R/L.',
              '```powershell',"& '.\\.venv\\Scripts\\python.exe' -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 1 --backend onnx --display --auto-glasses",'```','',
              'Với dashboard: đổi `run` thành `serve`; giữ cùng `--config`, `--source` và `--auto-glasses`. Nếu bỏ cờ `--auto-glasses`, runtime tiếp tục dùng nhánh gốc như trước. Chuyển tự động đang thử nghiệm; không tự bật cho mọi cấu hình trước khi có video RGB kính để nghiệm thu.',
              'Bộ nhận diện kính dùng MobileNetV3-Small, RGB128, ONNX CPU; bộ mắt kính vẫn YOLOv8n-cls RGB224. Nhãn kính từ CelebA chỉ dùng để nhận kính, không dùng làm nhãn mắt Open/Closed. [CelebA chính thức](https://mmlab.ie.cuhk.edu.hk/projects/CelebA.html); notebook gắn public input trực tiếp, không xuất lại dataset ảnh vào gói upload.',
              '', '### Việc cần làm để tăng chính xác trên camera USB','',
              '1. Quay video RGB có kính cận thật ở góc chính diện/chéo/thấp và gần–trung bình; đủ mở hai mắt, nháy riêng từng mắt, chớp cả hai, nhắm2giây và thay đổi phản sáng. Quay thêm người/gọng kính, giữ người hoặc buổi quay riêng cho validation/test.',
              '2. Dùng nguồn sáng tản, chỉnh vị trí camera/đèn để thấy được mi mắt và iris qua kính. Ảnh bị tròng kính phản sáng che mắt giữ UNKNOWN. Không tăng báo đúng bằng cách giảm ngưỡng.',
              '3. Xem và gán nhãn từng mắt trên frame/crop runtime; lời nhắc trong video không được lấy làm ground truth. Train trộn RGB kính, RGB không kính và MRL bổ sung; preprocessing phải trùng khi chạy.',
              '4. So sánh model trên clip RGB giữ riêng: F1 từng lớp, recall nhắm, lỗi Open→Closed có confidence, UNKNOWN và matrix; đo blink/sự kiện nhắm kéo dài theo thời gian. Chỉ dùng bản mới làm mặc định khi các tiêu chí camera đạt.',
              '', '### Lệnh thu video RGB mới','',
              'Đóng ứng dụng Camera của Windows. Clip đầu tiên dùng để kiểm tra ứng viên, không tự đưa vào train:','',
              '```powershell',"Set-Location -LiteralPath 'C:\\Users\\P1 Gen 5\\Downloads\\DA2'",
              "& '.\\.venv\\Scripts\\python.exe' tools/record_eye_glasses.py --source 1 --subject-id p01 --capture-group glasses_p01_test_01 --split test --distance medium",'```','',
              'Thời lượng mặc định75giây, nhắc động tác trên cửa sổ. Eye1/Eye2 theo số crop, không thêm nhãn R/L. Ghi FFV1 sạch, timestamp nguồn và metadata; không nối ESP32.',
              'Gán nhãn bằng `tools/annotate_eye_glasses.py --video <đường dẫn AVI>`: Space phát/dừng; J/K từng frame; A/D±10frame; 1 mở/mở; 2 nhắm/nhắm; 3 nhắm/mở; 4 mở/nhắm; 0 không rõ; X bỏ mốc cuối; S lưu. Không tự điền đầu/đuôi chưa xem. Công cụ giữ panel hướng dẫn ngoài hình để thấy mắt.',
              '', '### Quy trình RGB kính và Kaggle','',
              '[Hướng dẫn đầy đủ](../../data_collection/eye_glasses/RGB_WORKFLOW.md): quay → duyệt từng mắt → tạo crop đúng runtime → so sánh mắt gốc/mắt kính/tự chuyển → tạo bundle RGB mới → chuẩn bị notebook GPU. Mỗi bundle mới giữ riêng; không ghi đè dữ liệu hoặc job đã hoàn thành.',
              'Dữ liệu RGB mới được tách theo người/capture group. Gói train cần đủ train/val/test và hai lớp có nhãn đã duyệt. Sampling RGB kính45%, RGB hồi quy25%, MRL kính20%, MRL không kính10%; phần RGB kính có metric riêng, không gộp vào trung bình RGB cũ.',
              'Validation chặn tăng lỗi mở thành nhắm có confidence và giảm recall nhắm có confidence; cần tăng F1 RGB kính2 điểm. Test không chọn epoch. `evaluate_eye_glasses_rgb.py` xuất ma trận cả UNKNOWN và replay tự chuyển, không coi F1 crop là nghiệm thu blink tự nhiên.',
              'Quy trình này đã kiểm tra bằng fixture tổng hợp để xác minh packaging, metadata, pixel checksum và notebook; chưa có dataset RGB kính thật mới, chưa chạy đợt train RGB mới.',
              '', '### Tệp bàn giao','',
              '- [Metric CSV](metrics.csv), [PC verification](pc_verification.json), [model evaluation gốc](../../models/eye_glasses_adapted/evaluation.json).',
              '- [Ứng viên mắt kính và manifest](../../models/eye_glasses_adapted/manifest.json). `runtime.yaml` trong folder này là kiểm tra riêng model ứng viên; lệnh hệ thống tự động ở trên giữ manifest nền.',
              '- [Notebook bộ nhận diện kính](../../notebooks/eyewear_selector_gpu.ipynb), [kết quả và kiểm tra chuyển nhánh](automatic_routing/README.md).',
              '- [Dataset ZIP](../../kaggle_upload/glasses_adaptation_20261013.zip), [Notebook](../../notebooks/eye_glasses_gpu.ipynb).',
              f'- [Kaggle GPU Private](https://www.kaggle.com/code/{state["notebook_id"]}).',
              f'- SHA256 dataset ZIP `{bundle["sha256"]}`; output ZIP `{state["cloud_result"]["sha256"]}`.',
              '', '**Trạng thái mục tiêu: đang thực hiện. Còn thiếu video RGB đeo kính để xác nhận cải thiện trong điều kiện sử dụng thực tế.**','']
    (out/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    progress={'gpu_training':'COMPLETE','candidate_verified_pc':True,'IR_test_improved':True,'live_rgb_glasses_verified':False,
              'default_model_changed':False,'required_next_evidence':'Reviewed RGB glasses clip from USB camera; independent validation/test for further adaptation',
              'tests':'195 Python tests passed; 10 shared-client tests passed; TypeScript and web build passed','automatic_routing_implemented':True,
              'rgb_training_pipeline_ready':True,'rgb_camera_dataset_present':False,
              'automatic_routing_verified':False,'goal_completed':False}
    routing=out/'automatic_routing/verification.json'
    if routing.is_file():
        check=json.loads(routing.read_text(encoding='utf-8'))
        progress.update(automatic_routing_verified=check['passed'],known_no_glasses_clips=len(check['known_no_glasses_rgb_replays']))
    (out/'progress.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')
    collection=ROOT/'data_collection/eye_glasses/README.md'
    collection.write_text('# '+TITLE+'\n\n## Dữ liệu mắt khi đeo kính\n\n'+
        'MRL audit ở `mrl_audit/` là ảnh hồng ngoại đã xem kết quả; không dùng lại như test cuối. Video RGB mới ghi ở `videos/`.\n\n'+
        'Lệnh thu và cách gán nhãn: [Hướng dẫn nâng cấp](../../reports/glasses_adaptation_20261013/README.md).\n\n'+
        'Đã có ứng viên IR fine-tune; chưa có nghiệm thu RGB kính. Lời nhắc khi ghi không tự tạo nhãn mắt.\n',encoding='utf-8')
    with collection.open('a',encoding='utf-8') as stream:
        stream.write('\n[Quy trình RGB kính: quay, duyệt, đánh giá và fine-tune Kaggle](RGB_WORKFLOW.md).\n')
    print(json.dumps(progress,indent=2))


if __name__=='__main__':main()
