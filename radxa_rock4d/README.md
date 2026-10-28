# Radxa ROCK 4D — RK3576/RK3576J

Runtime chính là package dùng chung `driver_monitor` tại gốc dự án. Bộ cũ trong `python_runtime/` nay chuyển tiếp vào package đó; không duy trì hai bộ logic camera/thời gian riêng.

Xem [hướng dẫn triển khai đầy đủ](../DEPLOY_RADXA.md), [web/app và dịch vụ LAN](../DASHBOARD.md) và [báo cáo hiện tại](../reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.pdf).

`rknn_conversion/export_models.py` và `convert_onnx_to_rknn.py` là các wrapper tương thích cho exporter/converter dùng chung. Xuất `.pt → ONNX` ở môi trường PC; chuyển `ONNX → RKNN` trong venv Linux riêng với `requirements-host.txt` của thư mục conversion. SDK Toolkit2 2.3.2 dùng Torch ≤2.4.0, khác venv export PC Torch 2.6.0.

YuNet chạy CPU; classifier dùng ONNX CPU hoặc RKNN Lite2/NPU, với label/preprocessing đọc từ `../models/manifest.json`. `target_platform` là `rk3576`. Checkpoint gốc chỉ lưu ở `../camera_classical/`; thư mục runtime trên bo dùng manifest của package chung.

Lệnh tại gốc dự án trên bo:

```bash
.venv/bin/python -m driver_monitor run --source /dev/video0 --backend rknn --headless --esp32-port /dev/ttyUSB0
```

`python_runtime/run_camera.sh` cũng gọi lệnh này. Hai model nền RKNN đã chuyển thành công trong WSL; trọng số PC hiệu chỉnh hiện tại chưa chuyển RKNN. Tạo lại gói bằng `tools/build_radxa_bundle.py` sau khi chọn và chuyển đúng model. Bo chưa được setup, nên chưa có số đo NPU hoặc nghiệm thu phần cứng.
