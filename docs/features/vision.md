# Vision và chất lượng quan sát

## Hợp đồng

YuNet chạy CPU, tìm mặt và năm mốc: hai tâm mắt, mũi, hai khóe miệng.
Detector làm việc trên ảnh thu nhỏ; classifier nhận crop từ ảnh gốc theo config đã chọn.
Mốc cấu hình đang chọn: detector 320, confidence 0,8; eye ROI rộng 0,8d/cao 0,6d với d là khoảng
cách hai mắt; face margin 10%. Xem YAML/manifest để xác nhận giá trị thực trước khi sửa.

## Chất lượng và lỗi thường gặp

- Thiếu mặt, nhiều mặt không xác định được tài xế, tối/mờ/crop quá nhỏ → giữ quality và UNKNOWN.
- Eye quality có thể kém trong khi miệng vẫn hợp lệ; không loại ngáp chỉ vì mắt chưa chắc chắn.
- Khi đổi góc/ngẩng đầu, motion gate ngắt xác nhận mắt để tránh tính eye cycle giả.
- Hệ thống không tái tạo chi tiết mắt đã mất vì khoảng cách xa bằng cách resize lên 224×224.
- Overlay giữ khung mặt/mắt, không gắn R/L lên camera; nhãn bên trong dữ liệu không đồng nghĩa
  với vị trí trái/phải trên màn hình khi ảnh bị mirror.

## Camera USB trên Radxa

Mốc DV20 `/dev/video0`/`video1` chỉ là lần quan sát gần nhất; kiểm lại sau khi rút/cắm hoặc reboot.
Không dùng `video-dec0`/`video-enc0` như camera. Không diễn giải lỗi USB thành lỗi classifier.

```bash
lsusb -d 4c4a:4a55
v4l2-ctl --list-devices
sudo dmesg | tail -n 40
```

Quan sát phần cứng gần nhất: [radxa-setup](../evidence/2026-10-15-radxa-setup.md).

## Kiểm tra

```bash
python -m unittest tests.test_camera_quality tests.test_face_size_gate tests.test_head_motion -v
```

Đổi crop cần kiểm tra ảnh classifier thực nhận và đánh giá model lại; hạ quality gate cần số liệu
UNKNOWN, false closed và false yawn trên validation, không dựa vào một ảnh chụp.
