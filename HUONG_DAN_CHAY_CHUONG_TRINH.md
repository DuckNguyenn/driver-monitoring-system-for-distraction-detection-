# Tổng hợp các cách chạy chương trình DA2

Cập nhật 28/10/2026. Lệnh Windows bên dưới dùng **PowerShell**, chạy tại workspace DA2. `run` xử lý camera/video độc lập; `serve` chạy cùng nhận diện và cung cấp web/API cho máy tính, Android, iPhone. Chọn một cách tại một thời điểm nếu cùng dùng camera hoặc ESP32.

## 1. Chuẩn bị và chọn đúng model

```powershell
Set-Location "C:\Users\P1 Gen 5\Downloads\DA2"
.\.venv\Scripts\python.exe --version
```

Các ví dụ chính giữ profile người dùng đã chọn: `models/yawn_kaggle_near_medium/runtime.yaml`, gồm mắt `eye_refined_v4` và ngáp near/medium. Đã kiểm tra file model ONNX/PyTorch và checksum tại máy ngày 28/10.

| Cấu hình | Model được chọn |
| --- | --- |
| `models/yawn_kaggle_near_medium/runtime.yaml` | Profile near/medium người dùng chọn; dùng trong hướng dẫn này |
| `configs/camera_pc.yaml` | Profile camera PC khác, ngáp `yawn_camera_refined` |
| `configs/driver_monitor.yaml` trong checkout Windows | Manifest nền `models/manifest.json` |
| Hai YAML trong ZIP Radxa ONNX | Cùng trỏ manifest portable near/medium đã đóng gói |

Bỏ `--config`: `run` chọn driver_monitor.yaml, `serve` chọn camera_pc.yaml. Vì vậy các lệnh chính ghi cấu hình tường minh để giữ cùng model.

Nếu môi trường thiếu dependency, cài theo nhu cầu; môi trường hiện có không cần cài lại mỗi lần chạy:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-host.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.lock.txt
```

Lệnh đầu cài môi trường PC đầy đủ; lệnh sau bổ sung web/API. Máy mới cần tạo `.venv` bằng Python 3.12 trước khi cài; các model cục bộ bị Git ignore cần được sao chép đúng artifact/checksum.

## 2. Chạy camera trên PC, có cửa sổ

```powershell
.\.venv\Scripts\python.exe -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend onnx --display
```

`0` là chỉ số camera, không phải cổng COM. Nhấn Q/Esc trong cửa sổ hoặc Ctrl+C ở terminal để dừng. Khi cần xác định camera, dừng phiên đang giữ camera rồi chạy:
```powershell
.\.venv\Scripts\python.exe tools/probe_camera.py --indexes 0 1 2 3
```

## 3. Chạy camera không mở cửa sổ

```powershell
.\.venv\Scripts\python.exe -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend onnx --headless --duration 30 --log-dir logs/camera_headless
```

Chạy 30 giây rồi dừng; bỏ `--duration 30` để chạy đến khi Ctrl+C. Log gồm dữ liệu frame/sự kiện, CSV và summary; cấu trúc chi tiết xem [runtime](docs/features/runtime.md).

## 4. Chạy trên video đã ghi

Ví dụ dùng video dataset đang có tại máy:
```powershell
.\.venv\Scripts\python.exe -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source "data_collection/eye_medium/steady_open/20261013T015318_188531Z_eye.avi" --backend onnx --display --realtime --log-dir logs/video_replay
```

Thay `--source` bằng đường dẫn video khác. `--realtime` điều tiết tốc độ trình chiếu gần thời gian nguồn; bỏ cờ này để xử lý nhanh nhất có thể. Logic vẫn dùng timestamp video. Với nguồn camera, cờ này không tạo chế độ quay video.

## 5. Chạy bằng backend PyTorch

```powershell
.\.venv\Scripts\python.exe -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend torch --display
```

Backend thay đổi nhưng profile giữ nguyên. PyTorch cần dependency host và artifact `.pt`. Không đổi tên model hoặc preprocessing để chuyển backend.

## 6. Chạy nhận diện kèm web và API

```powershell
.\.venv\Scripts\python.exe -m driver_monitor serve --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend onnx --display --host 0.0.0.0 --port 8765 --preview-fps 5
```

- Trên PC: mở `http://127.0.0.1:8765`, nhập mã kết nối in trong terminal.
- Trên thiết bị cùng LAN: dùng `http://IP_CUA_MAY_CHAY_SERVE:8765`; xem IPv4 PC bằng `ipconfig` hoặc dòng LAN khi khởi động.
- Bỏ `--display` để serve chạy không màn hình. `--preview-fps 5` là mục tiêu truyền ảnh, không phải cam kết FPS suy luận.
- Muốn phát video lên web/app: thay `--source 0` bằng đường dẫn video và thêm `--realtime`.
- Ctrl+C dừng API. Đóng cửa sổ hình hoặc video kết thúc chỉ dừng suy luận; API có thể vẫn phục vụ lịch sử.

Web đã build tại `frontend/web/dist` và được Python phục vụ cùng API; cách này không cần bật Vite. Mã API khác mật khẩu SSH, cổng serial và QR Expo. Không ghi mã thật vào tài liệu.

## 7. ESP32: ESP-IDF và kết nối với chương trình Python

**Người dùng xác nhận nạp firmware bằng ESP-IDF.** Đã tìm thấy SDK `C:\Espressif\frameworks\esp-idf-v5.5.4` cùng `C:\esp\v6.0.1`; thư mục SDK không phải project firmware của DA2. Trong workspace hiện chỉ thấy sketch `.ino` tham khảo, chưa tìm được source ESP-IDF khớp giao thức còi DA2 trong các thư mục đã rà.

Khi đã xác định đúng project firmware, mở ESP-IDF Terminal đã cấu hình cho project đó. Thay đường dẫn và COM5 bằng giá trị thực:
```powershell
Set-Location "DUONG_DAN_PROJECT_FIRMWARE_ESP_IDF"
idf.py --version
idf.py build
idf.py -p COM5 flash monitor
```

Thoát IDF Monitor bằng **Ctrl+]** trước khi Python dùng cùng cổng. Dừng run/serve trước khi nạp lại firmware. Lệnh build/flash/monitor theo [tài liệu Espressif](https://github.com/espressif/esp-idf/blob/master/docs/en/get-started/start-project.rst); không tự đổi target hoặc SDK của project đã có.

Trở về PowerShell tại DA2; cổng COM5 dưới đây chỉ là ví dụ. Liệt kê cổng mà không mở serial:
```powershell
.\.venv\Scripts\python.exe -m serial.tools.list_ports
```

Kiểm tra giao thức sau khi firmware được nạp và monitor đã đóng; lệnh này gửi yêu cầu bật/tắt còi ngắn:
```powershell
.\.venv\Scripts\python.exe tools/test_esp32.py --port COM5
```

Chạy nhận diện và điều khiển ESP32:
```powershell
.\.venv\Scripts\python.exe -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend onnx --display --esp32-port COM5
```

Muốn kèm web/app, dùng lệnh ở mục 6 và thêm `--esp32-port COM5`. Firmware IDF cần tương thích host: serial 115200, lệnh `ALERT 1 <reasons>`/`ALERT 0`, phản hồi `OK ALERT 1`/`OK ALERT 0`. Watchdog, GPIO và mức điều khiển của firmware IDF thật cần đối chiếu source; GPIO25/watchdog 2 giây trong sketch tham khảo chưa chứng minh cấu hình firmware IDF đang nạp. Xem [ESP32](docs/features/esp32-alerts.md).

## 8. Android, LDPlayer và iPhone

Camera và AI chạy trên PC/Radxa; điện thoại/giả lập nhận dữ liệu của `serve` ở mục 6.

**Android APK / LDPlayer 9:** cài `dist/android/DriverMonitor.apk` (có thể kéo file vào LDPlayer), mở Driver Monitor, nhập IP LAN và mã API của máy chạy serve. APK đã đóng gói JavaScript, không cần terminal Expo. Không dùng `127.0.0.1:5555` của ADB làm địa chỉ API.

**Expo Go trên Android hoặc iPhone:** mở terminal PowerShell thứ hai tại DA2. Chạy `npm.cmd ci` khi chuẩn bị dependencies hoặc lockfile thay đổi; sau đó chọn một lệnh phù hợp:
```powershell
npm.cmd run start:mobile
```
Hoặc để thử Android bằng Expo Go:
```powershell
npm.cmd run start:android
```

Quét QR để tải app bằng Expo Go tương thích SDK 57, rồi nhập URL/mã API trong app. Giữ terminal Expo và serve. QR Expo khác mã kết nối API. `localhost` trên điện thoại không trỏ về PC. Ứng dụng hiện cảnh báo foreground; push nền/khóa màn hình chưa có. Xem [Android](docs/features/android.md), [iPhone](docs/features/iphone.md).

## 9. Web ở chế độ phát triển giao diện

Giữ serve chạy như mục 6; terminal thứ hai chạy:
```powershell
npm.cmd run dev:web
```

Mở URL Vite in ra, thường là `http://localhost:5173`; nhập URL API `http://127.0.0.1:8765` và mã của serve. Vite chỉ phục vụ giao diện, không chạy AI. Khi muốn dùng bản web tĩnh cùng Python:
```powershell
npm.cmd run build:web
```

Sau khi build xong, dùng lại web trên cổng 8765. Thông tin chi tiết ở [DASHBOARD](DASHBOARD.md).

## 10. Chạy trên Radxa qua SSH

Các lệnh sau là **Bash trên Radxa**, khác PowerShell. Áp dụng cho bộ portable ONNX `dist/DA2-radxa-onnx.zip` đã giải nén tại `~/DA2`; YAML trong ZIP đã chọn đúng model. Thư mục source Windows và bộ ZIP cũ không tự đồng bộ.
```bash
cd ~/DA2
# Chỉ khi thiết lập môi trường lần đầu:
bash scripts/setup_radxa.sh onnx
# Nhận diện camera, không mở cửa sổ:
.venv/bin/python -m driver_monitor run --source /dev/video0 --backend onnx --headless --duration 30 --log-dir logs/camera_cpu
```

Muốn xem qua web/app, dừng run trước, rồi:
```bash
cd ~/DA2
.venv/bin/python -m pip install -r requirements-dashboard.txt
.venv/bin/python -m driver_monitor serve --source /dev/video0 --backend onnx --host 0.0.0.0 --port 8765 --preview-fps 5
```

Mở `http://IP_LAN_RADXA:8765` trên thiết bị cùng LAN. Thêm `--esp32-port /dev/ttyUSB0` khi đã xác định đúng thiết bị; `/dev/ttyACM0` hoặc đường dẫn by-id cũng có thể được dùng. `--display` chỉ dành cho phiên có màn hình/desktop phù hợp, SSH headless dùng web.

Camera/serial có thể đổi sau rút/cắm. Kiểm tra `v4l2-ctl --list-devices`, `ls /dev/serial/by-id/` và `hostname -I` trên bo; không suy IP Radxa từ IP Windows. Xem [triển khai Radxa](DEPLOY_RADXA.md).

## 11. RKNN/NPU và tự khởi động bằng systemd

**RKNN:** chỉ dùng khi đúng model của profile đã chuyển sang RK3576, manifest có artifact RKNN và bo có runtime tương thích. Profile near/medium kiểm tra ngày 28/10 hiện chỉ có `torch`/`onnx`; đổi riêng cờ backend chưa tạo được model NPU.

Trong **bộ portable RKNN đã tạo và kiểm tra riêng**, lệnh chạy có dạng:
```bash
cd ~/DA2
.venv/bin/python -m driver_monitor run --source /dev/video0 --backend rknn --headless
```

Có thể dùng `serve` thay `run` trong bộ RKNN hợp lệ. Quy trình chuyển/build gói ở [Radxa](docs/features/radxa.md); RKNN nền cũ không đại diện cho model near/medium.

**systemd:** có mẫu [run](radxa_rock4d/systemd/driver-monitor@.service) và [dashboard](radxa_rock4d/systemd/driver-monitor-dashboard@.service). Hai mẫu hiện mặc định `/opt/driver-monitor` và RKNN; phải sửa WorkingDirectory/ExecStart, backend, config, camera và serial cho đúng nơi cài trước khi dùng với `~/DA2`/ONNX. Chọn một dịch vụ, xác minh chạy tay trước; lệnh dưới chỉ áp dụng sau khi service đã cài đúng:
```bash
sudo systemctl start driver-monitor-dashboard@radxa
sudo systemctl status driver-monitor-dashboard@radxa
journalctl -u driver-monitor-dashboard@radxa -f
sudo systemctl stop driver-monitor-dashboard@radxa
```

Thay `radxa` bằng user thực. Chỉ sau kiểm tra start/stop và tài nguyên thành công mới dùng `sudo systemctl enable driver-monitor-dashboard@radxa` nếu muốn tự khởi động. Không bật đồng thời dịch vụ run và dashboard cho cùng camera/ESP32. Tailscale vẫn hoãn theo yêu cầu.

## 12. Chạy riêng từng model và các bản đối chiếu

Kiểm tra đúng model mắt của profile đang chọn, kèm ảnh 224×224 đầu vào:
```powershell
.\.venv\Scripts\python.exe tools/test_original_model.py --name eye --use-config-model --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend onnx --inspect-model
```

Đổi `--name eye` thành `--name yawn` để kiểm tra ngáp. Thêm `--record --duration 30 --output-dir data_collection/model_check` nếu muốn ghi video/CSV để review. Công cụ này chỉ hiển thị xác suất thô, không chạy Monitor hoặc điều khiển ESP32. Bỏ `--use-config-model` sẽ chuyển sang checkpoint gốc, dù vẫn truyền config.

**Auto-glasses:** nhánh thử nghiệm, mặc định tắt. Nếu chủ động thử và có đủ hai artifact phụ, thêm `--auto-glasses` vào lệnh PC mục 2; không tự bật khi chạy thông thường hoặc trong ZIP Radxa hiện có. Xem [glasses](docs/features/glasses.md).

**Haar/FaceMesh cũ:** môi trường riêng cài `camera_classical/requirements.txt`, rồi chạy `camera_classical/camera_classical.py --camera 0 --eye-model camera_classical/best_eye.pt --yawn-model camera_classical/best_yawn.pt` bằng Python của môi trường đó. Đây là bản đối chiếu dùng model gốc, không phải đường chạy YuNet hiện tại. `radxa_rock4d/python_runtime/run_camera.sh` cũng thuộc bản cũ; xem [camera_classical](camera_classical/README.md).

**Launcher có sẵn:** `scripts/start_camera.cmd` mặc định camera_pc; có thể giữ model near/medium bằng `.\scripts\start_camera.cmd --config models/yawn_kaggle_near_medium/runtime.yaml`. `scripts/run_video.cmd "duong-dan-video.mp4"` không nhận thêm config, nên dùng manifest nền qua cấu hình mặc định run; ưu tiên lệnh video tường minh ở mục 4 nếu cần giữ near/medium.

## 13. Kiểm tra cấu hình, lệnh phụ và xử lý nhanh

Preflight kiểm dependency, manifest và checksum; không mở camera hay xác nhận còi:
```powershell
.\.venv\Scripts\python.exe -m driver_monitor preflight --config models/yawn_kaggle_near_medium/runtime.yaml --backend onnx --output reports/preflight_selected.json
```

| Lệnh CLI khác | Công dụng |
| --- | --- |
| `fetch-models` | Tải YuNet |
| `export`, `convert` | Xuất ONNX hoặc chuyển RKNN; có ghi artifact/manifest |
| `prepare-dataset`, `train` | Chuẩn bị dữ liệu, huấn luyện |
| `evaluate-classifier`, `parity` | Đánh giá classifier, so sánh backend |
| `evaluate-session`, `evaluate-study` | Đánh giá sự kiện và tổng hợp nghiên cứu |

Tra cú pháp bằng `.\.venv\Scripts\python.exe -m driver_monitor TEN_LENH --help`. Danh mục này là công cụ phát triển/đánh giá; không cần chạy trước mỗi phiên camera.

- Không thấy hình: cần `--display`; camera sai thì probe lại. `--rotate 90/180/270` xoay toàn khung khi cần.
- Cổng 8765 bận: Ctrl+C terminal serve cũ; hoặc dùng `--port 8766` và sửa URL trên client. Đổi cổng API không giải quyết camera/serial đang bị giữ.
- Cổng COM bận: đóng IDF Monitor và phiên host khác đang dùng cổng. ACK không chứng minh còi đã phát âm thực tế.
- App không kết nối: kiểm IPv4, cùng LAN, quyền mạng Private/local network và mã API; không dùng IP ADB hoặc localhost của điện thoại.
- `UNKNOWN` là thiếu quan sát/chất lượng; kiểm ánh sáng, nét và vị trí mặt trước khi điều chỉnh ngưỡng.
- Bản tổng hợp đã kiểm cú pháp CLI, cấu hình/checksum và sự có mặt của web/APK/ZIP; chưa chạy lại camera, flash ESP32 hoặc nghiệm thu Radxa trong lượt này.
