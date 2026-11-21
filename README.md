# HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ

DA2 dùng camera để theo dõi mắt nhắm kéo dài, chớp mắt và ngáp. PC hoặc Radxa ROCK 4D xử lý hình ảnh, xác nhận sự kiện theo thời gian và ghi nhật ký. Khi cần cảnh báo, máy xử lý gửi lệnh qua USB/serial cho ESP32 điều khiển còi. Người dùng có thể xem camera, trạng thái và lịch sử phiên trên web hoặc điện thoại trong cùng mạng LAN.

## Tiến độ đến ngày 22/11/2026

| Hạng mục | Kết quả hiện có | Việc còn cần xác nhận |
| --- | --- | --- |
| Radxa ROCK 4D và camera DV20 | Bo RK3576 đã chạy thử suy luận ONNX trên Debian 12 ARM64. Khi phát lại nhật ký một phiên DV20, phần mềm đếm được 13 chu kỳ ở một mắt, 11 ở mắt kia và 2 lần chớp đồng thời. | Đo FPS và độ trễ toàn hệ thống trên bo, chạy dài hạn và kiểm thử trên NPU. |
| Nhận diện ngáp | Bản thử ngày 18/11 được huấn luyện bổ sung bằng 95 ảnh cắt từ camera DV20. Khi phát lại clip đã dùng để huấn luyện, bộ đếm tăng từ 1 lên 6 đợt ngáp với cùng ngưỡng. [Kết quả và cách thử](models/yawn_radxa_20261118_candidate/HUONG_DAN_THU.md) | Đánh giá trên phiên camera độc lập, có cả ngáp, nói chuyện và cười. |
| ESP32 và còi | Firmware đã build bằng ESP-IDF 5.5.4. Ngày 13/11, log do người dùng cung cấp ghi nhận ESP32 trả lời lệnh cảnh báo qua COM5. [Kết quả thử serial](docs/features/esp32-alerts.md) | Nghe còi trên mạch thật và kiểm tra còi tự tắt khi mất liên lạc với máy xử lý. |
| Web, iPhone và Android | Dashboard và app Expo hiển thị khung hình, biểu đồ mắt/ngáp và lịch sử phiên, hỗ trợ xuất CSV. Người dùng đã xác nhận iPhone kết nối được. Bản Android đã thử trên giả lập LDPlayer. [Web](DASHBOARD.md) · [iPhone](docs/features/iphone.md) · [Android](docs/features/android.md) | Thử đầy đủ trên điện thoại thật với Radxa. App hiện hiển thị cảnh báo khi đang mở. |

YuNet xác định khuôn mặt và các điểm mốc để cắt vùng mắt và mặt. Hai bộ phân loại YOLOv8n-cls ước lượng trạng thái mắt và khả năng ngáp. Một chu kỳ mở–nhắm–mở có thể xuất hiện ở riêng một mắt. Bộ đếm chớp mắt chỉ tăng khi hai chu kỳ ngắn chồng nhau theo thời gian. Khi mất mặt hoặc ảnh không đủ rõ, tín hiệu tương ứng mang giá trị `UNKNOWN`. [Quy tắc xác nhận sự kiện và cảnh báo](docs/features/monitoring.md)

## Chọn cấu hình

| Môi trường | Cấu hình | Khi nào dùng |
| --- | --- | --- |
| Windows, sau khi clone repo | [configs/camera_pc.yaml](configs/camera_pc.yaml) | Mặc định cho camera PC. Dùng model mắt `eye_refined_v4` và model ngáp `yawn_camera_refined`. |
| Thử model ngáp ngày 18/11 | [runtime.yaml](models/yawn_radxa_20261118_candidate/runtime.yaml) | Repo có trọng số và manifest của bản thử. PyTorch và ONNX đã cho kết quả tương đương trên 12 mẫu ở PC. [Kết quả đối chiếu](models/yawn_radxa_20261118_candidate/pc_verification.json) |
| Radxa, gói triển khai cục bộ `dist/DA2.zip` | `configs/driver_monitor.yaml` hoặc `configs/dv20-blink-pose.yaml` trong ZIP | Gói dùng ONNX trên CPU với model ngáp DV20 đa góc. Cấu hình thứ hai dùng để thử bộ lọc chuyển động đầu khi đếm chớp mắt. |

Các lệnh cũ dùng `models/yawn_kaggle_near_medium/runtime.yaml` cần bộ model near/medium lưu tại máy. Khi clone từ GitHub, dùng cấu hình PC ở hàng đầu để chạy ngay. Các model RKNN nền trong repo dành cho RK3576 và dùng bộ trọng số riêng.

## Chạy trên Windows

Từ thư mục dự án, tạo môi trường Python 3.12 và kiểm tra model ONNX trong PowerShell.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-host.txt
.\.venv\Scripts\python.exe -m driver_monitor preflight --config configs/camera_pc.yaml --backend onnx
```

**Xem trực tiếp trên PC** bằng lệnh sau. Đổi `--source 0` theo chỉ số camera, hoặc thay bằng đường dẫn video và thêm `--realtime`. Nhấn `Q` hoặc `Esc` để thoát. Nếu dùng còi, thêm `--esp32-port` cùng cổng COM thực tế của ESP32.

```powershell
.\.venv\Scripts\python.exe -m driver_monitor run --config configs/camera_pc.yaml --source 0 --backend onnx --display
```

**Xem trên web hoặc điện thoại** bằng cách dừng phiên `run` trước để giải phóng camera, rồi khởi động máy chủ.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.lock.txt
.\.venv\Scripts\python.exe -m driver_monitor serve --config configs/camera_pc.yaml --source 0 --backend onnx --host 0.0.0.0 --port 8765
```

Mở `http://127.0.0.1:8765` trên PC, hoặc `http://<IPv4-của-PC>:8765` trên thiết bị cùng LAN. Nhập mã kết nối in trong terminal. Python phục vụ sẵn bản web đã build. Để thử app bằng Expo Go, mở terminal thứ hai, chạy `npm.cmd ci` rồi `npm.cmd run start:mobile`, quét mã QR và nhập địa chỉ máy chủ cùng mã kết nối.

## Chạy trên Radxa với gói DA2

Ví dụ sau dùng gói `DA2.zip` đã giải nén và cài môi trường tại `/root/DA2` trên bo. Kiểm tra đường dẫn camera và dừng phiên cũ trước khi chạy.

```bash
cd /root/DA2
.venv/bin/python -m driver_monitor serve --config configs/driver_monitor.yaml --source /dev/video0 --backend onnx --host 0.0.0.0 --port 8765 --preview-fps 5
```

Mở `http://<IPv4-của-Radxa>:8765` từ máy cùng LAN. Để thử đếm chớp mắt theo tư thế đầu, đổi riêng `--config` thành `configs/dv20-blink-pose.yaml`. Tham số `--preview-fps 5` đặt tốc độ gửi ảnh xem trước lên giao diện. [Hướng dẫn cài đặt Radxa](DEPLOY_RADXA.md)

## Kiểm thử và tài liệu

Ngày 22/11, 52 kiểm thử liên quan đến chuyển động mắt và đầu, sự kiện camera, firmware ESP-IDF trên máy tính và tài liệu đã đạt. Để chạy lại nhóm này trên Windows, dùng lệnh sau.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_eye_motion_profiles tests.test_camera_events tests.test_head_motion tests.test_esp32_idf tests.test_context_docs
```

Toàn bộ bộ kiểm thử Python của thư mục `tests` có thể chạy bằng `-m unittest discover -s tests -v`. Một số ca cần dữ liệu cục bộ và sẽ được bỏ qua nếu thiếu ảnh. Video cá nhân, dataset huấn luyện và log từng khung hình được lưu tại máy. [Dữ liệu kiểm thử](tests/fixtures/README.md) · [Quy trình thu dữ liệu](data_collection/README.md)

- [Hướng dẫn vận hành PC, web/app, ESP32 và Radxa](HUONG_DAN_CHAY_CHUONG_TRINH.md)
- [Nối dây, build và nạp firmware ESP-IDF cho ESP32](esp32_buzzer_idf/README.md)
- [Chín sơ đồ thiết kế hệ thống, bản duyệt ngày 14/11 (PDF)](BaocaoDA/So_do_duyet_20261114/SO_DO_HE_THONG_BAN_DUYET.pdf)
- [Báo cáo kỹ thuật (PDF)](reports/BAO_CAO_GIAM_SAT_BUON_NGU_CHINH_SUA.pdf) · [Bản Markdown](reports/BAO_CAO_GIAM_SAT_BUON_NGU_CHINH_SUA.md)
- [Bản đồ mã nguồn và tài liệu theo chức năng](CONTEXT-MAP.md) · [Checkpoint dự án](CHECKPOINT.md)
- [Nguồn model và giấy phép](models/README.md)
