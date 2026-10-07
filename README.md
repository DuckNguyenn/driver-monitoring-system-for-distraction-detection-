# Hệ thống giám sát trạng thái buồn ngủ của tài xế

Camera → YuNet → hai bộ phân loại YOLOv8n-cls (mắt/ngáp) → xác nhận theo thời gian → ESP32 → buzzer. Runtime dùng chung cho PC và Radxa ROCK 4D, hỗ trợ camera/video, ONNX/PyTorch/RKNN, chế độ không màn hình và nhật ký.

Model PC hiện tại được chọn bởi `configs/camera_pc.yaml`, dùng mắt `eye_refined_v4` và ngáp `yawn_camera_refined`. Hai file RKNN nền trong `models/` dành cho **RK3576**, dùng trọng số gốc; trọng số PC hiệu chỉnh chưa chuyển RKNN. Radxa chưa được setup và chưa có kết quả nghiệm thu NPU/còi trên thiết bị thật.

## Chạy camera trên Windows

Cần Python 3.12. Tại thư mục dự án, chạy PowerShell:

```powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-host.txt
& '.\.venv\Scripts\python.exe' -m driver_monitor preflight --config configs/camera_pc.yaml --backend onnx
& '.\.venv\Scripts\python.exe' -m driver_monitor run --config configs/camera_pc.yaml --source 0 --backend onnx --display
```

Đổi `--source 0` theo chỉ số camera do `tools/probe_camera.py` tìm được. Nhấn `Q`/`Esc` để thoát. Thêm `--esp32-port COM7` với cổng ESP32 thực tế nếu dùng buzzer.

Chạy video của bạn:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --config configs/camera_pc.yaml --source 'duong-dan-video.mp4' --backend onnx --display --realtime
```

## Kiểm thử và dữ liệu cục bộ

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '.\.venv\Scripts\python.exe' -m unittest discover -s camera_classical/tests -v
& '.\.venv\Scripts\python.exe' tools/verify_release.py
```

Repository chứa mã nguồn, model, manifest/checksum, notebook, sơ đồ và báo cáo. Dataset Kaggle/CEW/GENKI/SMILES, ảnh khuôn mặt hồi quy, video camera, log từng frame, môi trường Python và cache chỉ giữ tại máy. Các test cần ảnh cục bộ hiển thị `skipped` khi thiếu ảnh; test logic, capture, serial và adapter vẫn chạy. Xem [fixtures](tests/fixtures/README.md) và [quy trình dữ liệu](data_collection/README.md). `verify_release.py` ghi rõ số test bỏ qua và tình trạng thiếu bằng chứng video; dùng `--require-local-evidence` để yêu cầu đầy đủ dữ liệu kiểm thử cục bộ.

Các báo cáo sửa lỗi còn tham chiếu ảnh/log cục bộ phục vụ đối chiếu, không được đưa lên GitHub. Kết quả video một người đã dùng hiệu chỉnh model là bằng chứng phát triển, chưa chứng minh độ chính xác trên người mới.

[Kiểm tra bản GitHub](reports/github_repository_checks.json): bản tại máy đạt 69 test; bản xuất từ Git index đạt 56 test và bỏ qua 13 ca cần ảnh cục bộ. Model ONNX hiện tại đã qua checksum và suy luận thử; firmware đã qua mô phỏng host. Kiểm tra này dùng môi trường Python PC hiện có, chưa thay thế kiểm tra cài đặt/NPU trên Radxa.

## Tài liệu

- [Hướng dẫn camera, cấu hình và đánh giá](README_DRIVER_MONITOR.md)
- [Triển khai Radxa ROCK 4D](DEPLOY_RADXA.md)
- [ESP32 và sơ đồ nối buzzer](esp32_buzzer/README.md)
- [Cấu trúc thư mục](REPOSITORY_STRUCTURE.md)
- Báo cáo hoàn thiện: [Word](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.docx), [PDF](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.pdf)
- Kiến trúc model: [Word](reports/BAO_CAO_KIEN_TRUC_MODEL.docx), [PDF](reports/BAO_CAO_KIEN_TRUC_MODEL.pdf), [Markdown](reports/BAO_CAO_KIEN_TRUC_MODEL.md)

YuNet giữ giấy phép MIT đi kèm. Ultralytics YOLO và các dataset có giấy phép/điều khoản riêng; thông tin nguồn nằm trong [models/README.md](models/README.md) và các công cụ thu dữ liệu.
