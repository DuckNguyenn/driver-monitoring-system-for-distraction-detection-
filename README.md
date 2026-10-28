# HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ

> Tiếp tục theo feature: [bản đồ context](CONTEXT-MAP.md), [checkpoint mới nhất](CHECKPOINT.md), [docs](docs/README.md).

Camera → YuNet → hai bộ phân loại YOLOv8n-cls (mắt/ngáp) → xác nhận theo thời gian → ESP32 → buzzer. Runtime dùng chung cho PC và Radxa ROCK 4D, hỗ trợ camera/video, ONNX/PyTorch/RKNN, chế độ không màn hình và nhật ký.

Model PC hiện tại được chọn bởi `configs/camera_pc.yaml`, dùng mắt `eye_refined_v4` và ngáp `yawn_camera_refined`. Hai file RKNN nền trong `models/` dành cho **RK3576**, dùng trọng số gốc; trọng số PC hiệu chỉnh chưa chuyển RKNN. Radxa đã được người dùng setup Debian 12/Python 3.11 và chạy ONNX smoke; DV20 USB đã được nhận. FPS pipeline, NPU và còi thực tế vẫn chưa nghiệm thu; xem checkpoint có ngày.

Profile người dùng chọn trong lần triển khai gần nhất là `models/yawn_kaggle_near_medium/runtime.yaml`; khác profile mặc định ở trên. Bộ Radxa ONNX giữ profile near/medium này.

## Dashboard web và app iPhone

Hai giao diện tiếng Việt chỉ giám sát trong cùng Wi-Fi: camera, trạng thái, biểu đồ, thiết bị và lịch sử/CSV. Runtime tiếp tục xử lý tại PC/Radxa, web/app nhận kết quả của Monitor qua API. [Hướng dẫn đầy đủ và kết quả kiểm thử](DASHBOARD.md).

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dashboard.lock.txt
& '.\.venv\Scripts\python.exe' -m driver_monitor serve --source 0 --backend onnx --display
```

Mở `http://127.0.0.1:8765`, nhập mã hiện trong terminal. Máy khác/iPhone dùng IPv4 của PC. Web đã build được phục vụ cùng Python, không cần Node.js để vận hành. App thử bằng Expo Go: tại terminal khác chạy `npm.cmd ci`, rồi `npm.cmd run start:mobile`; quét QR bằng iPhone, nhập cùng IPv4 và mã. Web/app nhận khung hình Driver monitor, nén JPEG bất đồng bộ với mục tiêu 15 FPS; biểu đồ tách Mắt 1, Mắt 2 và Ngáp. Người dùng đã xác nhận app kết nối; nghiệm thu đầy đủ iPhone và Radxa còn chờ.

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

Ảnh/log cục bộ phục vụ đối chiếu không được đưa lên GitHub. Kết quả video một người đã dùng hiệu chỉnh model là bằng chứng phát triển, chưa chứng minh độ chính xác trên người mới.

[Kiểm tra bản GitHub](reports/github_repository_checks.json): bản tại máy đạt 69 test; bản xuất từ Git index đạt 56 test và bỏ qua 13 ca cần ảnh cục bộ. Model ONNX hiện tại đã qua checksum và suy luận thử; firmware đã qua mô phỏng host. Kiểm tra này dùng môi trường Python PC hiện có, chưa thay thế kiểm tra cài đặt/NPU trên Radxa.

## Tài liệu

- [Tổng hợp tất cả cách chạy: PC, video, web/app, ESP-IDF và Radxa](HUONG_DAN_CHAY_CHUONG_TRINH.md)
- [Hướng dẫn camera, cấu hình và đánh giá](README_DRIVER_MONITOR.md)
- [Triển khai Radxa ROCK 4D](DEPLOY_RADXA.md)
- [ESP32 và sơ đồ nối buzzer](esp32_buzzer/README.md)
- [Cấu trúc thư mục](REPOSITORY_STRUCTURE.md)
- [Fine-tune với ảnh mờ và kết quả thử nghiệm](reports/BLUR_REFINEMENT.md): hai model thử mới trong `models/blur_refined/`, dùng profile `configs/camera_blur_candidate.yaml`.
- Báo cáo hoàn thiện, gồm kiến trúc và lý thuyết thuật toán: [Word](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.docx), [PDF](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.pdf), [nguồn Markdown](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.md)

YuNet giữ giấy phép MIT đi kèm. Ultralytics YOLO và các dataset có giấy phép/điều khoản riêng; thông tin nguồn nằm trong [models/README.md](models/README.md) và các công cụ thu dữ liệu.
