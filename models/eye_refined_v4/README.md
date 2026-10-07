# Model mắt dùng thử trên PC

Checkpoint mắt trong thư mục này tiếp tục được tham chiếu bởi profile `configs/camera_pc.yaml` thông qua `../yawn_camera_refined/manifest.json`. Manifest trong thư mục này lưu bản phối hợp trước sửa ngáp, dùng qua `configs/camera_yawn_previous.yaml`. Kiến trúc mắt vẫn là YOLOv8n classification, 224×224, 1.440.850 tham số, thứ tự `Closed, Open`.

Fine-tune khối Classify gồm convolution 1×1, tham số affine BatchNorm và linear; backbone cùng thống kê BatchNorm giữ nguyên. Dùng vùng cắt YuNet `0,8d × 0,6d`. Model ngáp tham chiếu checkpoint đã hiệu chỉnh nụ cười ở `../smile_refined/best_yawn.pt`.

Nhãn mắt được xem riêng theo từng vùng cắt; không suy ra từ nhãn ngáp/cười. Ca lỗi mắt mở hẹp `file0127.jpg` được bổ sung vào train làm hard negative. Các kết quả ca này chỉ là kiểm thử hồi quy. Thông tin nhãn và lịch sử nằm trong `data_reviews/eye_roi_labels*.json`; số liệu kiểm tra trong `evaluation.json`, `validation.json` và `reports/EYE_CLASSIFIER_FIX.md`.

Có checkpoint PyTorch và ONNX kèm checksum. Chưa xuất RKNN cho trọng số này, chưa đo NPU hay nghiệm thu video cabin theo người. `models/eye_refined` được giữ để khởi tạo lớp Linear khi huấn luyện lại bằng `tools/refine_eye_tail.py`. Các artifact v2 và kết quả thử v3 không được sử dụng đã được dọn; cache đặc trưng v2 vẫn được giữ vì bước tạo dữ liệu v4 còn đọc nó.
