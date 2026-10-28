# Dataset và notebook ngáp gần/trung bình

- Dataset tải lên Kaggle: `yawn_near_medium_dataset.zip` (ảnh cá nhân, giữ Private).
- Notebook import: [`yawn_near_medium_kaggle.ipynb`](../notebooks/yawn_near_medium_kaggle.ipynb).
- Tạo lại gói từ dữ liệu đã xác minh: `python tools/build_yawn_kaggle_bundle.py`.

Gói gồm 255 crop camera train (167 `no_yawn`, 88 `yawn`), 320 ảnh static train và 160 ảnh static validation. Crop giữ kích thước/tỷ lệ gốc; notebook giảm độ phân giải/blur trước preprocessing 224×224 dùng chung với runtime. Nhãn cười thuộc `no_yawn`; các đoạn chuyển tiếp/nói chuyện chưa chắc chắn không được tự gán nhãn. Hai clip gần/trung bình không đổi khỏi split train. Không có clip xa hoặc clip lỗi đã khóa trong gói.

Checkpoint có sẵn: model Kaggle ban đầu `camera_classical/best_yawn.pt` và bản `models/yawn_usb_robust/best_yawn.pt`. Mặc định bắt đầu từ bản USB, không bắt đầu từ ứng viên CPU vừa train. Chỉ train model ngáp. Bộ nguồn preprocessing/augmentation được đóng gói cùng dataset và kiểm tra hash; không cần tải repo/cache hoặc video gốc lên Kaggle.

Tạo Kaggle Dataset Private từ ZIP, import notebook, Add Input dataset đó, bật **Settings → Accelerator → GPU** và Internet cho bước cài dependency, rồi Run All. Notebook tìm dataset tự động; nếu thiếu CUDA sẽ dừng, không chuyển sang CPU. Dùng GPU đầu tiên kể cả khi chọn T4 ×2. Giữ CUDA-enabled PyTorch/torchvision của Kaggle; notebook ghim các thư viện còn lại. [Hướng dẫn Kaggle](https://www.kaggle.com/docs/notebooks).

Batch mặc định 64, 40 epoch, LR `1e-4`, early stopping 8 epoch, AMP. Chọn checkpoint bằng static validation và kiểm tra hồi quy theo nguồn, cả recall tại 0,70. Sau lưu PT, validation được đo lại; ONNX probabilities opset 12 được kiểm tra graph/parity trên crop camera và static. Backbone/BN buffers, thứ tự lớp, preprocessing và ngưỡng runtime được giữ nguyên.

Đầu ra: `yawn_kaggle_result.zip`. Giải nén **vào `yolov10n/models/`**, để có `models/yawn_kaggle_near_medium/runtime.yaml`, rồi chạy:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend onnx --display
```

Validation hiện có là ảnh tĩnh cũ; chưa có camera validation mới/người độc lập. Thử nghiệm CPU với cùng hai clip đã xác nhận 4/4 ngáp trên train, nhưng không xác nhận ngáp trong clip USB góc thấp giữ riêng; ở clip ngáp ngắn cự ly trung bình, confidence cải thiện nhưng chưa đủ thời gian xác nhận. Vì thế bản thử chưa được thay vào profile chính. Tăng GPU/epoch không chứng minh đã sửa lỗi góc camera; cần bổ sung clip đa góc và validation mới. Không diễn giải train replay hay static F1 thành nghiệm thu sự kiện/báo nhầm theo giờ.

Gói đã được kiểm tra tại máy Windows. `bundle_verification.json` ghi số file/ảnh, dung lượng và SHA của ZIP thực tế. Theo yêu cầu setup cloud ngày 11/10/2026, **Dataset Private phiên bản 2** và **notebook Private phiên bản 2** đã chạy hoàn tất trên Tesla T4: 19 epoch, chọn epoch 11. Gói PT/ONNX đã tải về `models/yawn_kaggle_near_medium/`; kiểm tra runtime PC trên 48 crop khớp nhãn và đạt parity. Xem [CLOUD_TRAINING.md](../CLOUD_TRAINING.md) để chạy thử, xem môi trường thực và tình trạng MCP. Chưa nghiệm thu sự kiện camera mới hoặc chuyển RKNN/đo trên Radxa. Ảnh/checkpoint không đưa lên GitHub.
