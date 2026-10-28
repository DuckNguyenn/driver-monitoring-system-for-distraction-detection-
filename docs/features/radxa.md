# Triển khai Radxa ROCK 4D

## Mốc thực tế

Đọc [bằng chứng setup](../evidence/2026-10-15-radxa-setup.md) trước khi dùng kết quả từ runbook cũ.
Bo RK3576, Debian 12 ARM64/Python 3.11.2 đã cài và chạy ONNX smoke theo terminal người dùng.
Camera DV20 đã enumeration thành công nhưng chưa có số đo pipeline/FPS/latency từ phiên bo.
NPU, ESP32/buzzer và chạy liên tục 2 giờ chưa có bằng chứng nghiệm thu.

## Bộ đóng gói đang dùng

`dist/DA2-radxa-onnx.zip`, nguồn `models/yawn_kaggle_near_medium/runtime.yaml`.
Packager giữ crop/quality/monitor config, copy artifact theo manifest và đổi đường dẫn portable.
Hai YAML portable cùng chọn model đã đóng gói; không copy Windows venv/dataset/video cá nhân.
Hash và kiểm tra ZIP lịch sử nằm tại `reports/bundle_verification_onnx.json`.

```powershell
& '.\.venv\Scripts\python.exe' tools/build_radxa_bundle.py --backend onnx --config models/yawn_kaggle_near_medium/runtime.yaml --output dist/DA2-radxa-onnx.zip
& '.\.venv\Scripts\python.exe' tools/verify_bundle.py --bundle dist/DA2-radxa-onnx.zip
```

Các lệnh build tạo artifact mới; không chạy lại chỉ để đọc docs hoặc thay file checkpoint.
Bộ ZIP cũ đã chuyển không tự nhận các docs/code mới trong worktree Windows.

## CPU và NPU

- Script setup kiểm Linux ARM64/RK3576, Python 3.10–3.12, dependencies và model smoke.
- ONNX CPU dùng onnxruntime 1.20.1; Toolkit2/Lite2 của nhánh NPU đang ghim 2.3.2.
- Model near/medium hiện chọn chỉ có torch/ONNX; chuyển rk3576 trong Linux trước khi build RKNN.
- RKNN nền cũ và report simulator cũ không phải bằng chứng NPU cho model fine-tune mới.
- Auto-glasses đang không được packager đóng gói; cờ đó bị từ chối để tránh artifact thiếu.
- setup_rknn_host.sh còn đường convert baseline mặc định; chọn đúng manifest khi chuyển bản hiện dùng.

## Thao tác

[DEPLOY_RADXA](../../DEPLOY_RADXA.md) giữ hướng dẫn dài. Kiểm đúng camera/serial trước khi chạy
systemd; template cũ mặc định RKNN và `/opt/driver-monitor`, không áp dụng trực tiếp cho bộ CPU ở `~/DA2`.
`run --headless` qua SSH không mở cửa sổ; dùng serve để xem camera từ web/app.
Chỉ bật một process sở hữu camera và xác minh cleanup/tắt còi trước khi chạy tự động.
