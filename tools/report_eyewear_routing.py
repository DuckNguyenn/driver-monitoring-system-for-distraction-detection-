"""Measured RGB eyewear selector, routing replay and explicit evidence limits."""
import json
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=ROOT/'reports/glasses_adaptation_20261013/automatic_routing';out.mkdir(parents=True,exist_ok=True)
    report=json.loads((ROOT/'models/eyewear_selector/evaluation.json').read_text())
    measured=json.loads((out/'verification.json').read_text())
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,key,title in zip(axes,('test_raw','test_gate'),('Phân loại xác suất ≥0,5','Ngưỡng chọn nhánh kính đã khóa')):
        metric=report[key];matrix=np.asarray(metric['confusion_matrix'])
        ax.imshow(matrix,cmap='Blues');labels=['Không kính','Có kính']
        ax.set_xticks([0,1],labels);ax.set_yticks([0,1],labels);ax.set_xlabel('Dự đoán');ax.set_ylabel('Thực tế')
        ax.set_title(title)
        for (i,j),n in np.ndenumerate(matrix):ax.text(j,i,str(n),ha='center',va='center',fontsize=16,color='white' if n>matrix.max()/2 else '#153139')
    fig.tight_layout();fig.savefig(out/'selector_confusion_matrix.png',dpi=165);plt.close(fig)
    gate=report['test_gate'];raw=report['test_raw'];fmt=lambda x:f'{100*x:.2f}%'
    lines=['# HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ','',
           '## Bộ nhận diện kính và chuyển nhánh mắt tự động','',
           'Đã huấn luyện bộ chọn riêng trên GPU, tích hợp runtime và kiểm tra phát lại. Nhánh mắt không kính và ngáp giữ nguyên checkpoint/crop/ngưỡng. Chưa có video RGB đeo kính cận của người dùng để nghiệm thu độ chính xác nhánh mắt kính và blink.','',
           '```mermaid','flowchart LR','  C[Camera USB] --> V[YuNet và crop runtime]','  V --> G[MobileNetV3-Small · kính RGB128]',
           '  G --> T[Confidence và xác nhận 1,5 giây]','  T --> O[Mắt gốc · khi không chắc hoặc không kính]',
           '  T --> S[Mắt chuyên kính · YOLOv8n-cls]', '  V --> Y[Ngáp · model hiện có]',
           '  O --> M[Monitor thời gian]','  S --> M','  Y --> M','  M --> B[ESP32 → Buzzer]','  M --> D[PC · web · app]','```','',
           '### Dữ liệu và quy trình','',
           '- [CelebA chính thức](https://mmlab.ie.cuhk.edu.hk/projects/CelebA.html), public Kaggle input `jessicali9530/celeba-dataset`, chỉ dùng thuộc tính Eyeglasses. Không dùng nhãn kính để tự gán trạng thái Open/Closed.',
           '- 10.000 crop train (5.000/lớp), 2.600 validation và 2.600 test (mỗi bộ: 2.000 không kính, 600 có kính). Dùng partition được cung cấp; chưa tự kiểm toán identity-disjoint vì mirror không có bảng identity.',
           '- YuNet và mở rộng mặt 10% như runtime; giữ ảnh qua cổng chất lượng. Loại mẫu trùng input pixel giữa các phần. Nghiệm thu detector face/quality cho ảnh ngoài bộ này vẫn cần đánh giá riêng.',
           '- MobileNetV3-Small khởi tạo ImageNet; train trên '+report['gpu']+', AdamW LR0,0002, weight decay0,0001, batch128, seed42, 10epoch, AMP. Crop gốc jitter/gamma/downsample/blur nhẹ trước resize, không augment validation/test.',
           '- Input RGB128, PIL bilinear resize cạnh ngắn/center crop, mean [0,485; 0,456; 0,406], std [0,229; 0,224; 0,225]. Đây là preprocessing riêng của bộ kính; preprocessing mắt/ngáp không thay đổi.',
           f'- Chọn epoch {report["selected_epoch"]} và ngưỡng {report["threshold"]:.9f} bằng validation: precision kính ≥99,5%, FPR không kính ≤0,2%, rồi tối đa recall. Mục tiêu validation không bảo đảm đúng trên camera khác.',
           '- Bộ kính ONNX CPU đo tối đa 2Hz; xác nhận1,5giây; điểm đo quá0,8giây coi thiếu. Chỉ model mắt đổi. Gap/mất mặt/đổi tài xế/score không chắc trả về mắt gốc. Một frame chuyển nhánh ngắt chuỗi mắt, không ngắt EMA/đợt ngáp.',
           '', '### Test tĩnh đã khóa','',
           '| Chính sách | Accuracy | F1 macro | Precision kính | Recall kính | Không kính chọn nhầm kính |',
           '|---|---:|---:|---:|---:|---:|']
    for name,metric in (('Ngưỡng0,5',raw),('Ngưỡng chuyển nhánh',gate)):
        lines.append('| '+name+' | '+' | '.join(fmt(metric[k]) for k in ('accuracy','macro_f1','glasses_precision','glasses_recall','no_glasses_false_route_rate'))+' |')
    lines += ['', '![Ma trận bộ nhận diện kính](selector_confusion_matrix.png)','',
              'Đây là kết quả nhận kính trên ảnh CelebA, không phải F1 mắt hay độ chính xác cảnh báo. Nhãn kính không chứng minh loại kính cận/trong suốt; cần kiểm tra phản sáng/tròng tối và giữ UNKNOWN khi không thấy mắt.',
              '', '### Kiểm tra phát lại video không kính','',
              '| Clip | Frame | Chuyển nhầm nhánh kính | Xác suất mắt/ngáp, trạng thái, bộ đếm khác |','|---|---:|---:|---:|']
    for item in measured['known_no_glasses_rgb_replays']:
        lines.append(f'| {Path(item["source"]).name} | {item["frames"]} | {item["wrong_specialist_switches"]} | {sum(item["differences"].values())} |')
    parity=measured['parity']
    lines += ['',f'Đối chiếu GPU Torch/PC ONNX: {parity["samples"]} tensor, sai lệch xác suất lớn nhất {parity["gpu_torch_vs_pc_onnx_max_delta"]:.3e}, lệch argmax {parity["argmax_mismatches"]}.',
              'Video là dữ liệu phát triển đã biết của cùng một người. Kết quả giữ nguyên trên các clip này chưa bảo đảm không bao giờ chọn nhầm với người/kính/camera mới.',
              '', '### Lệnh chạy','', '```powershell',
              "Set-Location -LiteralPath 'C:\\Users\\P1 Gen 5\\Downloads\\DA2'",
              "& '.\\.venv\\Scripts\\python.exe' -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 1 --backend onnx --display --auto-glasses",'```','',
              'Web/app: dùng `serve` với cùng tham số. Preview có `eye:original` / `eye:glasses`. Nếu bỏ `--auto-glasses`, model/logic cũ tiếp tục chạy. Không tự bật nhánh thử nghiệm cho mọi profile.',
              '', '### Độ trễ và giới hạn','',
              'Các summary trong [verification.json](verification.json) có FPS và processing p95 của từng lần replay gốc/tự động. Đây là PC offline headless, chưa phải đo đồng thời camera live/web/iPhone hay Radxa. Thứ tự chạy và cache ảnh có thể ảnh hưởng throughput; không dùng một cặp đo làm cam kết tốc độ.',
              'Chưa có video kính cận RGB để đo từng mắt, blink/nhắm kéo dài và UNKNOWN; chưa nghiệm thu cảnh báo sai/giờ, khả năng tự chuyển lúc tháo/đeo kính hoặc phản sáng thật. Model mắt kính hiện chỉ cải thiện có đo trên MRL hồng ngoại.',
              '', '### Tệp kết quả','',
              '- [Evaluation bộ kính](../../../models/eyewear_selector/evaluation.json), [manifest](../../../models/eyewear_selector/manifest.json), [verification](verification.json).',
              '- [Notebook GPU](../../../notebooks/eyewear_selector_gpu.ipynb), [kết quả mắt kính](../README.md), [ma trận mắt kính](../mrl_glasses_comparison.png).','']
    (out/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(out/'README.md')


if __name__=='__main__':main()
