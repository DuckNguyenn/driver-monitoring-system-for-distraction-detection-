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

## Profile giảm chặn chuyển động đang thử nghiệm

Mặc định `eye_motion_mode: geometry`, smoothing `0` giữ cách đo cũ và fingerprint cũ.
Chế độ `pose` chuẩn hóa ba mốc mắt/mũi theo trung điểm và khoảng cách hai mắt trước khi đo:
dịch chuyển đồng đều hoặc thay đổi kích thước ảnh không tự gây `head_motion`.
Độ lệch tương đối của mũi và góc đường nối hai mắt vẫn dùng để phát hiện đổi tư thế.
Đây là tín hiệu hình học 2D, không phải góc quay đầu 3D đã hiệu chuẩn.

[camera_video_pose_candidate.yaml](../../configs/camera_video_pose_candidate.yaml) giữ nguyên
manifest near/medium, crop, confidence mắt 0,8, điều kiện blink và kiểm tra chất lượng ảnh.
Chỉ đổi năm tham số: mode `pose`, EMA theo thời gian có hằng số 0,1 s,
settle 0,15 s, shift/shape ratio 0,3 và roll 6°. Cửa sổ so sánh vẫn 0,3 s.
Lọc chỉ áp dụng cho phép đo chuyển động; không sửa ảnh hoặc xác suất classifier.
Mất mặt, ảnh mờ/tối và điểm mốc không hợp lệ vẫn không cung cấp bằng chứng mắt.
Đổi track, timestamp lùi/lặp hoặc khoảng cách frame lớn hơn giới hạn sẽ xóa lịch sử lọc.

Chạy thử video đã cắt trong workspace (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m driver_monitor run --config configs/camera_video_pose_candidate.yaml --source .cache/video-review-20261106/clips/01_yawn_clear.mp4 --backend onnx --display --realtime
```

Ngày 07/11: clip 01 đủ 1.320 frame, `head_motion` từ 1.067 xuống 159; blink từ 0 lên 3,
gồm lần đã quan sát ở khoảng 1,4 s được xác nhận tại 1,60 s. Chạy CLI khớp với replay.
Clip không có mặt giữ 600/600 frame UNKNOWN; ảnh mặt mở xoay 15° không tạo eye cycle giả.
[Bằng chứng sáu clip](../evidence/2026-11-07-eye-motion-candidate.json) là dữ liệu phát triển,
chưa có nhãn đầy đủ để kết luận độ chính xác hoặc chọn làm mặc định.
Đoạn nói chuyện/quay đầu vẫn bị model ngáp đếm 2 lần mỗi clip ở cả hai profile;
khi mắt ít bị chặn, trạng thái WARNING do các lần ngáp này xuất hiện nhiều hơn.
Chưa kiểm chứng camera trực tiếp, Radxa hoặc ESP32 với profile này.

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
python -m unittest tests.test_camera_quality tests.test_face_size_gate tests.test_head_motion tests.test_eye_motion_profiles -v
```

Đổi crop cần kiểm tra ảnh classifier thực nhận và đánh giá model lại; hạ quality gate cần số liệu
UNKNOWN, false closed và false yawn trên validation, không dựa vào một ảnh chụp.
