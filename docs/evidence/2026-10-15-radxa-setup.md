# Bằng chứng setup Radxa đến 2026-10-15

Nguồn: ảnh và terminal người dùng gửi trong chat 14–15/10/2026, Asia/Bangkok.
Đây là bản chép chọn lọc không chứa mật khẩu/token; agent chưa điều khiển trực tiếp bo.

## Môi trường và artifact

- SSH đích ở lần gửi cuối: `radxa@192.168.2.38`; cần xác minh khi đổi mạng.
- `Linux rock-4d-spi ... aarch64`, kernel `6.1.84-13-rk2410-nocsf`.
- Debian GNU/Linux 12/bookworm, Python 3.11.2; script xác nhận `RK3576 detected`.
- File `DA2-radxa-onnx.zip` đã SCP thành công và giải nén vào `/home/radxa/DA2`.
- SHA256 của ZIP được kiểm tại PC:
  `2a962b44c3f1ff61ccad62156c028323dd06a51cde47cb152dfdcbdaa24cef06`.
- Đây là số hash artifact đóng gói cũ; chưa chạy đối chiếu checksum trên bo từ xa.

## Suy luận thử CPU

Script cài đặt đã hoàn tất với các dòng người dùng cung cấp:

```text
Report: reports/radxa_preflight.json
eye {'Closed': 0.9573370075622647, 'Open': 0.04266299243773531}
yawn {'no_yawn': 0.49274706840515137, 'yawn': 0.5072529315948486}
Inference smoke passed. Configure camera ROI and ESP32 port before enabling the service.
```

Script dùng ảnh zero 224×224: chỉ chứng minh model khởi tạo/chạy được, không đo chất lượng AI.
`reports/bundle_verification_onnx.json` tại PC vẫn là kiểm thử đóng gói lịch sử có `physical_board_tested=false`;
không sửa ngược file lịch sử đó để làm nó đại diện cho quan sát mới từ chat.

## Camera

Trước đó không có camera trong `lsusb`; có lỗi descriptor -32/-71 và ngắt USB sau khi nhận UVC.
Lần người dùng gửi sau cùng:

```text
Bus 003 Device 027: ID 4c4a:4a55 Jieli Technology USB Composite Device
USB Composite Device: DV20 USB  (usb-xhci-hcd.1.auto-1.1):
        /dev/video0
        /dev/video1
        /dev/media0
```

Enumeration thành công không chứng minh capture ổn định hoặc đủ 15 FPS.
Chưa có summary của lệnh chạy 30 giây trên bo. Chưa kết luận node `/dev/video1` là nguồn hình.

## Kết nối và phần còn thiếu

- Windows Tailscale đã được kiểm qua local API: `BackendState=Running`, `SelfOnline=true`.
- Chưa thấy peer khớp hostname `radxa|rock-4d` khi kiểm trên Windows; tên máy khác vẫn có thể tồn tại.
- Chưa có IP Tailscale Radxa, kết quả iPhone 4G, HTTPS hoặc thông báo khóa màn hình.
- Chưa có NPU inference, thông số FPS/latency 30 giây/2 giờ, serial ESP32 hoặc quan sát buzzer thật.
- Không diễn giải banner ngáp/nhắm mắt thành nhận diện tai nạn hoặc tình trạng y tế khác.

Bước tiếp theo nằm trong [CHECKPOINT](../../CHECKPOINT.md) và [remote-access](../features/remote-access.md).
