# HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ

## Nâng cấp mắt với kính cận trên camera RGB

Model mắt kính MRL và bộ tự nhận kính đã có. Độ chính xác khi đeo kính cận trước camera USB còn cần video thật có nhãn. Các bước dưới đây giữ model mắt gốc, model ngáp và các ngưỡng runtime; ứng viên mới xuất ra thư mục riêng. Chỉ huấn luyện trên Kaggle GPU.

### 1. Thu clip kiểm tra trước khi train thêm

Đóng Windows Camera và tiến trình đang dùng camera USB. Đeo kính cận/trong suốt, nhìn thấy mắt qua tròng. Camera hiện dùng index1; nếu thay thứ tự thiết bị, dùng công cụ probe để kiểm tra index.

```powershell
Set-Location -LiteralPath 'C:\Users\P1 Gen 5\Downloads\DA2'
& '.\.venv\Scripts\python.exe' tools/record_eye_glasses.py --source 1 --subject-id p01 --capture-group glasses_p01_test_01 --split test --distance medium
```

Clip75giây có lời nhắc mở mắt, nháy từng mắt, chớp cả hai, nhắm2giây và thay đổi phản sáng. Lời nhắc không tự tạo nhãn. Dữ liệu ghi FFV1 sạch và timestamp thực; không điều khiển ESP32. Clip `test` giữ làm kiểm tra, không chuyển sang train sau khi thấy model nhận sai.

### 2. Duyệt nhãn từng mắt

Mở file vừa ghi trong công cụ bằng tham số `--video`:

```powershell
& '.\.venv\Scripts\python.exe' tools/annotate_eye_glasses.py --video 'đường dẫn AVI vừa ghi'
```

Space phát/dừng; J/K từng frame; A/D±10frame. Phím1: mở/mở, 2: nhắm/nhắm, 3: nhắm/mở, 4: mở/nhắm, 0: không rõ cả hai, 5: không rõ/mở, 6: mở/không rõ. X bỏ mốc cuối; S lưu. Eye1/Eye2 theo số crop; không thêm nhãn R/L. Chỉ gán khoảng đã xem, phần đầu/đuôi chưa duyệt không được tự điền. Công cụ lưu `.eyes.csv` cạnh AVI.

### 3. So sánh model hiện có trên clip test

```powershell
& '.\.venv\Scripts\python.exe' tools/build_eye_glasses_rgb.py --collection data_collection/eye_glasses/videos --output data_collection/eye_glasses/rgb_supplement_eval
& '.\.venv\Scripts\python.exe' tools/evaluate_eye_glasses_rgb.py --data data_collection/eye_glasses/rgb_supplement_eval --split test
```

Kết quả mới lưu trong `reports/glasses_rgb_evaluation/<thời điểm>/`: `evaluation.json`, `predictions.csv`, `comparison_matrix.png` và replay logs. Ma trận so sánh mắt gốc, mắt chuyên kính và tự chuyển model; hàng là nhãn thật, cột là Nhắm/Mở/UNKNOWN. Từng mắt được chấm độc lập, không coi nháy một mắt là chớp cả hai. Khi chuyển model hoặc mắt không đủ chất lượng, kết quả tương ứng giữ UNKNOWN.

Đánh giá này đo phân loại từng mắt và hiệu quả chọn model trên clip. Số liệu blink tự nhiên, sự kiện nhắm kéo dài và cảnh báo sai/giờ vẫn cần đối chiếu sự kiện theo thời gian, không suy ra từ F1 crop. `--skip-replay` chỉ đo crop tĩnh và không đủ để kết luận hệ thống tự chuyển đúng. Replay luôn tắt giao tiếp còi.

### 4. Nếu cần fine-tune bằng RGB kính

Thu thêm người và buổi quay cho train/validation. Trong bộ RGB mới, một người và capture group chỉ thuộc một split. Người đã dùng cho test không đưa vào train hoặc validation. Khuyến nghị theo kế hoạch tổng thể: ít nhất5 người, ít nhất2 người giữ cho test, nhiều góc và gần–trung bình. Ngưỡng tối thiểu20 crop/lớp/split chỉ giúp công cụ từ chối gói thiếu dữ liệu, không phải tiêu chí nghiệm thu hoặc số mẫu độc lập.

Sau khi có các clip train/val/test đều đã duyệt:

```powershell
& '.\.venv\Scripts\python.exe' tools/build_eye_glasses_rgb.py --collection data_collection/eye_glasses/videos --output data_collection/eye_glasses/rgb_supplement_training
& '.\.venv\Scripts\python.exe' tools/build_glasses_bundle.py --rgb-supplement data_collection/eye_glasses/rgb_supplement_training --starting-eye-manifest models/eye_glasses_adapted/manifest.json --output-bundle kaggle_upload/glasses_rgb_adaptation
& '.\.venv\Scripts\python.exe' tools/prepare_glasses_cloud.py --archive kaggle_upload/glasses_rgb_adaptation.zip
```

Lệnh cuối tạo dataset input/notebook Private trong `kaggle_upload/glasses_cloud/<run-id>/`, in đường dẫn và lưu `latest-prepared.json`. Nó chỉ chuẩn bị file, chưa gửi job. `latest.json` và bundle/log của lần train đã hoàn thành được giữ nguyên. Sau khi kiểm tra gói, dùng Kaggle CLI với đường dẫn tuyệt đối được in: `datasets create -p <dataset_dir> --dir-mode zip`, tiếp đến `kernels push -p <notebook_dir>`; dùng Python trong `.venv-cloud` như các lần trước.

Notebook giữ backbone trước C2f cuối và BN running buffers; chỉ C2f cuối và Classify được fine-tune. Crop RGB đúng preprocessing hiện tại: native eye → augmentation nhẹ → RGB224 resize/center crop. Sampling: RGB kính45%, RGB hồi quy25%, MRL kính20%, MRL không kính10%; từng nhóm cân bằng Nhắm/Mở.

Validation RGB kính phải tăng F1 ít nhất2 điểm, không tăng mắt mở bị khẳng định nhắm và không giảm recall nhắm có confidence. Đồng thời kiểm tra hồi quy RGB cũ/IR. Test không dùng để chọn epoch hay ngưỡng. Nếu không đạt, notebook chỉ xuất báo cáo, không thay model. Các split mới chỉ độc lập trong giai đoạn fine-tune này; không chứng minh độc lập với lịch sử train checkpoint cũ.

Ứng viên mới cần xuất riêng, kiểm tra Torch/ONNX, phát lại test giữ riêng và xác minh tự chuyển model. Không ghi đè `eye_refined_v4`, model ngáp hoặc model kính đang được dùng khi chưa có bằng chứng tốt hơn.
