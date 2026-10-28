"""Summarize an MRL classifier audit without presenting it as live-video evidence."""
from pathlib import Path
import csv
import json

ROOT=Path(__file__).resolve().parents[1]
TITLE='HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ'


def main():
    out=ROOT/'reports/eye_glasses_20261013'
    report=json.loads((out/'evaluation.json').read_text(encoding='utf-8'))
    models=report['models']
    current=models['current_eye_v4']['by_condition']
    def percent(n):return f'{100*n:.2f}%'
    lines=['# '+TITLE,'','## Đánh giá model mắt với kính và nháy mắt','',
           '**Model nhận được một phần ảnh có kính, nhưng chưa đủ ổn định để xác nhận chất lượng khi người dùng đeo kính cận trước camera USB.**','',
           '### Dữ liệu đã lấy và giới hạn','',
           '- Đã tải bản [MRL trên Kaggle](https://www.kaggle.com/datasets/tauilabdelilah/mrl-eye-dataset) do người dùng cung cấp: 84.898 ảnh.',
           '- [MRL chính thức](https://mrl.cs.vsb.cz/eyedataset.html) mô tả ảnh mắt hồng ngoại có nhãn người, kính, mắt mở/nhắm, mức phản sáng, ánh sáng và cảm biến. Tên ảnh giữ nguyên thứ tự nhãn: subject, image, gender, glasses, eye state, reflections, lighting, sensor.',
           '- Nhãn kính chỉ có có/không; không cho biết độ cận hay kính trong suốt/kính râm. Người dùng hiện dùng kính cận/trong suốt.',
           '- Mẫu audit gồm 1.024 crop: 256 nhắm + 256 mở khi đeo kính, 256 nhắm + 256 mở không kính. Chọn bằng metadata, round robin theo người/điều kiện; không dựa vào xác suất model.',
           '- **Split test của bản Kaggle thiếu hoàn toàn nhóm đeo kính–mắt nhắm**: test có 1.566 ảnh không kính nhắm, 960 không kính mở, 697 đeo kính mở. Vì vậy audit cân bằng lấy thêm ảnh từ train gốc và không được coi là test độc lập.',
           '- Không thấy ảnh trùng byte/input RGB224 với các record huấn luyện PC đã lưu trong số ứng viên đã kiểm tra. Điều này chưa chứng minh model gốc chưa từng học MRL: nguồn train checkpoint gốc chưa đầy đủ, JPEG/resize khác cũng có thể không trùng hash.',
           '- Không huấn luyện mới trong phép audit; giữ nguyên ba checkpoint và preprocessing runtime RGB224. Mẫu cân bằng/điều kiện không phải phân bố tự nhiên của người lái xe.',
           '- Chỉ đưa ảnh mắt đã cắt vào classifier. Chưa đánh giá YuNet, chất lượng cả khuôn mặt, kính che mắt, motion gate, blink/ngáp tự nhiên hoặc còi bằng camera live.',
           '', '### Model mắt đang dùng — eye_refined_v4','',
           '| Nhóm | Ảnh | Accuracy argmax | F1 macro | Recall nhắm | Recall mở |',
           '|---|---:|---:|---:|---:|---:|']
    for glasses,label in ((False,'Không kính'),(True,'Đeo kính')):
        metric=current[f'glasses={glasses}']
        lines.append(f'| {label} | {metric["samples"]} | {percent(metric["accuracy"])} | {percent(metric["macro_f1"])} | {percent(metric["per_class"]["Closed"]["recall"])} | {percent(metric["per_class"]["Open"]["recall"])} |')
    lines += ['', 'Nhóm đeo kính: 90/256 ảnh nhắm bị dự đoán mở và 43/256 ảnh mở bị dự đoán nhắm. Đây là lỗi phân loại từng ảnh, chưa phải số sự kiện bỏ sót hay báo nhầm khi lái xe. Các nhóm khác nhau về người/điều kiện nên phép so sánh không chứng minh chỉ riêng kính gây ra chênh lệch.','',
              '![Ma trận mắt có và không kính](current_confusion_matrix.png)','',
              'Hàng là nhãn thực tế; cột là nhãn dự đoán. Ngưỡng confidence 0,8 được giữ nguyên. Biểu đồ bên phải chỉ áp dụng confidence, chưa áp dụng cổng chất lượng camera.',
              '', '| Nhóm | Coverage ở confidence ≥0,8 | Recall nhắm có confidence | Open → Closed có confidence | UNKNOWN |',
              '|---|---:|---:|---:|---:|']
    for glasses,label in ((False,'Không kính'),(True,'Đeo kính')):
        gate=current[f'glasses={glasses}']['confidence_and_quality_gate']
        lines.append(f'| {label} | {percent(gate["coverage"])} | {percent(gate["per_class"]["Closed"]["recall"])} | {gate["confusion_matrix_with_unknown"][1][0]} | {gate["unknown_samples"]} |')
    lines += ['', 'Không giảm confidence để giấu lỗi. Ngay cả confidence cao, nhóm kính vẫn có 73 ảnh nhắm bị khẳng định là mở và 29 ảnh mở bị khẳng định là nhắm. Nếu mắt bị tròng kính/ánh sáng che đến mức không đọc được, cần giữ UNKNOWN theo chất lượng quan sát thay vì gán nhãn chắc chắn.',
              '', '### So sánh checkpoint','',
              '| Checkpoint | Accuracy không kính | Accuracy có kính | F1 macro có kính |','|---|---:|---:|---:|']
    for name,model in models.items():
        groups=model['by_condition'];metric=groups['glasses=True']
        lines.append(f'| {name} | {percent(groups["glasses=False"]["accuracy"])} | {percent(metric["accuracy"])} | {percent(metric["macro_f1"])} |')
    lines += ['', 'Bản multiview vẫn là thử nghiệm. Chênh lệch vài ảnh trên audit này chưa đủ để chọn thay model đang chạy.',
              '', '### Phản sáng và ánh sáng','',
              '| Mức phản sáng trên mẫu đeo kính | Ảnh | Accuracy | Recall nhắm |','|---|---:|---:|---:|']
    for value,name in ((0,'Không'),(1,'Nhỏ'),(2,'Lớn')):
        groups=current[f'reflection={value}']['groups']
        metric=groups.get('glasses/glasses/IR_native_crop')
        if metric:
            lines.append(f'| {name} | {metric["samples"]} | {percent(metric["accuracy"])} | {percent(metric["per_class"]["Closed"]["recall"])} |')
    lines += ['', 'Đây là thống kê mô tả theo annotation MRL, không phải phép thử có kiểm soát. MRL sử dụng hồng ngoại; phản sáng trên camera USB RGB có thể khác.',
              '', '### Nháy một mắt và chớp hai mắt','',
              '- YOLO phân loại từng crop thành Closed/Open. Nó không có lớp wink/blink; sự kiện được Monitor ghép theo thời gian.',
              '- Nháy một mắt: kỳ vọng một chu kỳ mắt riêng tăng, blink both không tăng, không bật còi do nhắm hai mắt.',
              '- Chớp cả hai mắt: chỉ cặp chu kỳ có khoảng nhắm chồng nhau, kéo dài 0,05–0,5 giây mới tăng blink both. Nhắm hai mắt đủ 1,5 giây là điều kiện cảnh báo riêng.',
              '- **18 test hiện có đã đạt**: logic nháy riêng, chớp hai mắt, chuyển tiếp không chắc chắn và test tích hợp dùng các crop thật. Test dùng crop ghép hoặc chuỗi xác suất không thay thế video nháy mắt tự nhiên với kính.',
              '- Chưa có nhãn thời gian đầy đủ cho video người dùng đeo kính; recall wink/blink, sự kiện nhắm kéo dài và báo nhầm/giờ vẫn chưa đo.',
              '', '### Quay kiểm tra với kính cận và camera USB','',
              'Đóng ứng dụng Camera của Windows trước. Dùng model đang chạy, camera rời source 1:','',
              '```powershell',"Set-Location -LiteralPath 'C:\\Users\\P1 Gen 5\\Downloads\\DA2'",
              "& '.\\.venv\\Scripts\\python.exe' tools/test_original_model.py --name eye --use-config-model --config models/yawn_kaggle_near_medium/runtime.yaml --backend onnx --source 1 --inspect-model --record --duration 75 --output-dir data_collection/eye_glasses/videos",'```','',
              'Giao thức gợi ý, không dùng thời gian nhắc làm nhãn tự động:','',
              '1. 0–15 giây: đeo kính, giữ đầu yên, mở hai mắt; chớp tự nhiên.',
              '2. 15–30 giây: nháy mắt trái 5 lần, nghỉ rõ giữa các lần.',
              '3. 30–45 giây: nháy mắt phải 5 lần.',
              '4. 45–60 giây: chớp cả hai mắt 5 lần; sau đó nhắm cả hai khoảng 2 giây, mở lại.',
              '5. 60–75 giây: mở mắt và quay/ngẩng đầu nhẹ để quan sát phản sáng. Nếu không thấy mắt do kính phản sáng, giữ nhãn không chắc chắn.',
              '', 'Công cụ này ghi ảnh gốc, CSV xác suất từng mắt và input 224 để đối chiếu. Nó kiểm tra classifier; chạy `driver_monitor run` mới quan sát bộ đếm/còi theo thời gian. Nếu muốn so sánh trực tiếp với không kính, quay một clip thứ hai cùng vị trí/ánh sáng.',
              '', '### Tệp và tái lập','',
              '- [Evaluation JSON](evaluation.json), [xác suất từng ảnh](predictions.csv), [metric CSV](metrics.csv).',
              '- [Metadata mẫu](../../data_collection/eye_glasses/mrl_audit/dataset.json); các PNG gốc ở cùng thư mục.',
              '- ZIP tải ở `.cache/mrl_glasses/kaggle/mrl-eye-dataset.zip`.',
              '- Chạy lại: `.venv/Scripts/python.exe -X utf8 tools/evaluate_eye_glasses.py`, rồi `tools/report_eye_glasses.py`.',
              f'- SHA256 archive: `{report["archive_sha256"]}`.',
              '', '### Hướng fine-tune tiếp theo','',
              'Kính cận/trong suốt cần có dữ liệu RGB từ đúng camera USB, đa dạng gọng và phản sáng, với nhãn từng mắt mở/nhắm riêng. Giữ người/buổi quay riêng cho validation/test, dùng cùng quy trình crop, đưa các tình huống không đọc được thành UNKNOWN. MRL có thể làm dữ liệu bổ sung hồng ngoại; không thay thế hoàn toàn video RGB có kính. Bộ audit này đã được xem kết quả, nên không được tái sử dụng như một test cuối chưa từng xem.','']
    (out/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    rows=[]
    for name,model in models.items():
        for glasses in (False,True):
            metrics=model['by_condition'][f'glasses={glasses}']
            for kind,metric in (('argmax',metrics),('confidence_0.8',metrics['confidence_and_quality_gate'])):
                for label,value in metric['per_class'].items():
                    rows.append({'model':name,'glasses':glasses,'mode':kind,'class':label,**value,
                                 'accuracy':metric['accuracy'],'macro_f1':metric['macro_f1'],'coverage':metric['coverage']})
    with (out/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    data_dir=ROOT/'data_collection/eye_glasses'
    (data_dir/'README.md').write_text('# '+TITLE+'\n\nThu dữ liệu kính cận và mắt mở/nhắm/nháy mắt.\n\n'+
        'Mẫu MRL đã dùng audit nằm trong `mrl_audit/`. Đây là ảnh hồng ngoại, thiếu độc lập với training lịch sử; '+
        'không dùng lại audit như test cuối. Video RGB mới ghi vào `videos/`, cần xem và gán nhãn từng mắt theo thời gian.\n\n'+
        'Xem [kết quả và giao thức ghi](../../reports/eye_glasses_20261013/README.md).\n',encoding='utf-8')
    print(json.dumps({'report':str(out/'README.md'),'metrics_rows':len(rows),'live_glasses_video_measured':False},ensure_ascii=False))


if __name__=='__main__':main()
