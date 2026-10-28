# Triển khai trên Radxa ROCK 4D

> Tiếp tục theo feature: [bản đồ context](CONTEXT-MAP.md), [checkpoint mới nhất](CHECKPOINT.md), [docs](docs/README.md).

**Trạng thái 14/10/2026:** chưa có bằng chứng chạy trên bo. Model mắt/ngáp hiện dùng trong `models/yawn_kaggle_near_medium/runtime.yaml` có ONNX; gói `dist/DA2-radxa-onnx.zip` giữ đúng model, crop và ngưỡng thời gian của profile này, đã kiểm tra relocation/checksum/inference/API trên PC. Hai `.rknn` nền RK3576 cũ được Toolkit2 2.3.2 tạo trong Ubuntu WSL thuộc checkpoint nền; chưa phải RKNN của profile hiện dùng. Phải chuyển đúng manifest trước khi tạo gói NPU. Nhánh tự nhận kính vẫn thử nghiệm và chưa được công cụ này đóng gói.

ROCK 4D dùng RK3576/RK3576J theo [thông tin phần cứng Radxa](https://docs.radxa.com/en/rock4/rock4d/hardware-use/hardware-info). Converter dùng `target_platform="rk3576"`. SDK tham chiếu là [Rockchip v2.3.2](https://github.com/airockchip/rknn-toolkit2/tree/v2.3.2).

## 1. Kiểm tra hệ điều hành và thiết bị

Cài image Linux ARM64 chính thức cho đúng ROCK 4D theo [hướng dẫn Radxa](https://docs.radxa.com/en/rock4/rock4d/getting-started). Sau lần boot đầu, lưu kết quả:

```bash
uname -a
cat /etc/os-release
python3 --version
tr '\0' '\n' </proc/device-tree/compatible
ls -l /dev/video* /dev/ttyUSB* /dev/ttyACM*
```

Script cài đặt kiểm tra ARM64, RK3576 và Python 3.10–3.12. Nếu OS dùng Python khác, cần môi trường Python tương thích và wheel SDK tương ứng; không thay Python hệ thống. Kiểm tra RAM thực bằng `free -h`. Camera USB UVC và ESP32 kết nối qua USB; camera CSI cần cấu hình driver riêng của image Radxa.

Cài thư viện hệ thống Debian cần thiết:

```bash
sudo apt update
sudo apt install python3-venv libgl1 libglib2.0-0 v4l-utils
v4l2-ctl --list-devices
```

User chạy ứng dụng cần quyền `video`, `dialout`. Ví dụ với user đang đăng nhập:

```bash
sudo usermod -aG video,dialout "$USER"
```

Đăng nhập lại để quyền nhóm có hiệu lực. Dùng đường dẫn `/dev/serial/by-id/...` cho ESP32 nếu có để giữ đúng thiết bị sau khởi động.

## 2. Chạy bản ONNX CPU trước

Tạo ZIP trên PC:

```powershell
& '.\.venv\Scripts\python.exe' tools/build_radxa_bundle.py --backend onnx --config models/yawn_kaggle_near_medium/runtime.yaml --output dist/DA2-radxa-onnx.zip
```

Chép `dist/DA2-radxa-onnx.zip` vào bo, giải nén vào một thư mục làm việc và chạy từ gốc gói. Các YAML trong gói đã trỏ về manifest và model được đóng gói; không dùng lại đường dẫn Windows:

```bash
bash scripts/setup_radxa.sh onnx
.venv/bin/python -m driver_monitor run --source /dev/video0 --backend onnx --headless --duration 20 --log-dir reports/camera_cpu
```

Để xem trên web/iPhone, cài dependency API rồi chạy `serve` thay cho `run` (không chạy cả hai cùng sở hữu camera):

```bash
.venv/bin/python -m pip install -r requirements-dashboard.txt
.venv/bin/python -m driver_monitor serve --source /dev/video0 --backend onnx --host 0.0.0.0 --port 8765 --preview-fps 5
```

Dùng địa chỉ IP LAN của Radxa và mã kết nối được lệnh `serve` in ra. Đo FPS/độ trễ trên bo; ONNX CPU chưa được chứng minh đạt ≥15FPS trên ROCK4D.

Script tạo venv cục bộ, cài các phiên bản đã ghim, tạo `reports/radxa_preflight.json`, kiểm tra checksum và chạy suy luận thử cả hai classifier. Nó không cài driver NPU hoặc cấu hình camera CSI. `rock4d_matches` và suy luận smoke chưa chứng minh đạt FPS/độ chính xác.

## 3. Chuyển ONNX sang RKNN trên Linux

ONNX/manifest trong `models/` đã được xuất và so sánh trên PC. Nếu cần xuất lại `.pt`, dùng **môi trường PC hiện tại**:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor export
```

Chuyển RKNN trong **venv Linux riêng**. Bộ export PC dùng Torch 2.6.0; Toolkit2 2.3.2 yêu cầu Torch ≤2.4.0 trong [dependency chính thức](https://github.com/airockchip/rknn-toolkit2/blob/v2.3.2/rknn-toolkit2/packages/x86_64/requirements_cp312-2.3.2.txt). Không trộn hai môi trường.

Trong WSL2/Linux x86_64, chép/checkout thư mục dự án, rồi:

```bash
python3 -m venv .venv-rknn
.venv-rknn/bin/python -m pip install -r radxa_rock4d/rknn_conversion/requirements-host.txt
.venv-rknn/bin/python -m pip check
.venv-rknn/bin/python -m driver_monitor convert --manifest models/yawn_kaggle_near_medium/manifest.json
```

Nếu pip không có wheel phù hợp, lấy wheel đúng Python/kiến trúc từ [gói Toolkit2 chính thức](https://github.com/airockchip/rknn-toolkit2/tree/v2.3.2/rknn-toolkit2/packages). Converter khởi đầu không lượng tử hóa, tạo `models/best_eye.rknn`, `models/best_yawn.rknn`, lưu hash, đích và SDK vào manifest sau khi cả hai thành công.

Nếu Linux host chỉ có Python 3.13/3.14, `bash scripts/setup_rknn_host.sh` chuẩn bị Python 3.12.10, Torch CPU và SDK trong thư mục dự án bằng [uv 0.9.16](https://github.com/astral-sh/uv/releases/tag/0.9.16), xác minh checksum bản tải và gọi converter. Không cần thay Python hệ thống. Snapshot dependency Linux nằm ở `requirements-rknn-linux.lock.txt`; bằng chứng chuyển thành công sẽ nằm ở `reports/rknn_conversion.json`. Đây là script cho Linux x86_64, khác script setup ARM64 trên bo.

INT8 chỉ thử sau khi có crop train thật:

```bash
.venv-rknn/bin/python -m driver_monitor convert --manifest models/manifest.json --calibration data_collection/crops
```

Cần ≥200 bản ghi calibration **train-only** cho mỗi classifier, được `prepare-dataset` tạo với RGB/224 đúng preprocessing và kiểm tra hash. Chọn dữ liệu đa dạng ánh sáng/người/kính. Không dùng test để calibration. Giữ bản không lượng tử hóa để đối chiếu trước khi thay model triển khai.

Tạo gói NPU trong thư mục dự án có `.rknn` mới:

```bash
.venv-rknn/bin/python tools/build_radxa_bundle.py --backend rknn --config models/yawn_kaggle_near_medium/runtime.yaml --output dist/DA2-radxa-rknn.zip
```

Công cụ sẽ từ chối nếu thiếu bất kỳ artifact RKNN nào. Gói chứa runtime dùng chung, YuNet, hai model đã chọn, YAML, manifest, firmware và hướng dẫn; không mang venv Windows/dataset/video cá nhân sang bo.

## 4. Kiểm tra NPU và tương đương model

Trên bo, giải nén gói RKNN, giữ Toolkit2/Lite2 cùng **2.3.2**:

```bash
bash scripts/setup_radxa.sh rknn
.venv/bin/python -m driver_monitor preflight --backend rknn --output reports/npu_preflight.json
.venv/bin/python -m driver_monitor run --source /dev/video0 --backend rknn --headless --duration 20 --log-dir reports/camera_npu
```

[Lite2 ARM64 chính thức](https://github.com/airockchip/rknn-toolkit2/tree/v2.3.2/rknn-toolkit-lite2/packages) có wheel Python 3.10/3.11/3.12. Runtime model đã nhúng normalization `/255`; adapter nhận RGB `uint8` NHWC và không chia thêm lần nữa. YuNet tiếp tục chạy CPU.

Preflight lưu phiên bản package, OS/kernel, board compatible, checksum model, thông tin driver NPU nếu đọc được và hash `librknnrt.so` tại các vị trí thông dụng. Xác minh driver/thư viện đi cùng BSP/SDK của image; nếu load/init_runtime lỗi, lưu lỗi và xử lý bộ SDK/driver trước. Không coi việc SDK hỗ trợ RK3576 là bằng chứng driver hiện có trên bo đã tương thích.

Để đo giảm F1, chạy ONNX và RKNN trên **cùng tập crop test độc lập** trên bo và đối chiếu `.pt` đã đo trên PC. Hai báo cáo có cùng danh sách mẫu/hashes; cần giảm F1 ≤2 điểm phần trăm. Gói NPU giữ model ONNX đối chiếu; không cần cài PyTorch trên bo:

Chép tập crop test đã tách người từ PC vào `data_collection/crops/` trên bo trước khi chạy các lệnh sau.

```bash
.venv/bin/python -m pip install onnxruntime==1.20.1
.venv/bin/python -m driver_monitor parity --name eye --backend rknn --reference onnx --data data_collection/crops/eye --output reports/eye_npu_parity.json
.venv/bin/python -m driver_monitor parity --name yawn --backend rknn --reference onnx --data data_collection/crops/yawn --output reports/yawn_npu_parity.json
```

Đây là phép so sánh trên bo; kiểm tra simulator Toolkit2 trên PC được lưu riêng và không thay thế nó.

Simulator đã kiểm tra 20 ảnh mỗi classifier, đồng nhất nhãn 40/40 với ONNX; đó là graph dựng từ cùng nguồn/cấu hình, chưa chạy blob xuất ra trên NPU.

## 5. ESP32, ROI và chạy tự khởi động

Nạp [esp32_buzzer/esp32_buzzer.ino](esp32_buzzer/esp32_buzzer.ino), kiểm tra [nối dây/ACK/watchdog](esp32_buzzer/README.md). Chạy tay trước:

```bash
.venv/bin/python tools/test_esp32.py --port /dev/ttyUSB0
.venv/bin/python -m driver_monitor run --source /dev/video0 --backend rknn --headless --esp32-port /dev/ttyUSB0 --duration 30
```

Sửa `serial_port` và `driver_roi` trong `configs/driver_monitor.yaml` cho vị trí tài xế thực. Có thể xem từ HDMI bằng `--display` để căn camera trước khi chạy headless.

Mẫu [driver-monitor@.service](radxa_rock4d/systemd/driver-monitor@.service) dùng thư mục `/opt/driver-monitor`, backend **RKNN**, camera `0` mặc định và user instance. Sau khi chép toàn bộ gói vào đường dẫn này và tạo venv tại đó, thực hiện với user thực (ví dụ `radxa`):

```bash
sudo mkdir -p /opt/driver-monitor/logs
sudo chown radxa:radxa /opt/driver-monitor/logs
sudo cp radxa_rock4d/systemd/driver-monitor@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now driver-monitor@radxa.service
systemctl status driver-monitor@radxa.service
journalctl -u driver-monitor@radxa.service -n 100 --no-pager
```

`radxa` là ví dụ, thay bằng user hiện có. Venv/thư mục model cần đọc được bởi user đó. Service chỉ cho ghi `logs/`, restart khi lỗi và dừng trong 5 s; gửi `SIGTERM` làm runtime tắt còi rồi đóng tài nguyên. Camera khác chỉ số 0 cần thêm `--source` vào `ExecStart` trước khi cài service. Mẫu này chỉ dùng sau khi RKNN inference, camera và serial đã chạy tay thành công.

## 6. Nghiệm thu thực tế

Để dùng dashboard web trong cùng Wi-Fi sau khi chạy model/camera thành công, xem [DASHBOARD.md](DASHBOARD.md). Gói mới kèm `frontend/web/dist` và dependency API đã ghim; Radxa không cần Node.js để phục vụ web. Dịch vụ `driver-monitor-dashboard@.service` chạy lệnh `serve`, thay cho dịch vụ `run` nếu chọn giao diện web. Chỉ bật một dịch vụ sở hữu camera và ESP32. Model PC hiện tại có thể đóng gói riêng bằng `--manifest models/yawn_camera_refined/manifest.json --backend onnx`; gói RKNN vẫn cần manifest có trọng số NPU đúng phiên bản.

| Việc cần đo | Cách thu bằng chứng |
|---|---|
| ≥15 FPS, p95 đọc frame→quyết định ≤200 ms | Camera 640×480 trên bo, CSV/summary, CPU/RAM/nhiệt độ trong JSONL |
| Còi ≤300 ms sau xác nhận | Video/audio hoặc đo GPIO và timestamp/ACK; độ trễ quyết định chưa phải độ trễ còi |
| 2 giờ vận hành | `run --duration 7200 --headless --esp32-port ...`; lưu toàn bộ log và nhiệt độ |
| Camera bị rút | `UNKNOWN`/lỗi camera, lệnh tắt, ghi lỗi; service khởi động lại khi lỗi |
| Serial bị rút/model bị treo/process bị dừng | ESP32 tắt ≤2 s sau lệnh hợp lệ cuối; reconnect có ACK và log khi nối lại |
| Mất mặt/che mắt/nhiều mặt | `UNKNOWN`, không tích thời gian nhắm mắt qua đoạn thiếu dữ liệu |
| AI và sự kiện | Test tách người theo [quy trình dữ liệu](data_collection/README.md); báo cáo theo người/ánh sáng |

Các số nghiệm thu trên bo hiện để trống. Báo cáo PC và fixture kỹ thuật không thay thế các phép đo này.
