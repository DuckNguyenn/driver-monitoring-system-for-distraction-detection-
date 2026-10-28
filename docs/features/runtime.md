# Runtime camera và video

## Hợp đồng

Runtime điều phối lấy frame, Vision, classifier, Monitor, cảnh báo và nhật ký.
Chọn source bằng camera index hoặc `/dev/videoX`; video dùng timestamp nguồn, camera dùng monotonic.
Camera giữ frame mới nhất; video xử lý tuần tự. Frame cũ/gap/chất lượng thấp không được cộng thành
chuỗi mắt nhắm hợp lệ. Cleanup phải đóng capture/model/serial và yêu cầu tắt còi.

## Ranh giới thay đổi

- `run` hoạt động độc lập; `serve` thêm observer/preview mà không tự tính lại quyết định.
- API/network chậm không được chặn xác nhận theo thời gian hoặc heartbeat ESP32.
- YAML chọn manifest; đường dẫn YAML tương đối theo file, CLI tương đối theo working directory.
- Một camera/serial chỉ có một runtime sở hữu. Client web/iPhone là bên theo dõi.

## Đọc thêm khi cần

- [Tổng hợp các cách chạy](../../HUONG_DAN_CHAY_CHUONG_TRINH.md): PC/video, web/app, ESP-IDF/serial, Radxa và các đường chạy có điều kiện; cập nhật 28/10/2026.
- [Hướng dẫn chạy đầy đủ](../../README_DRIVER_MONITOR.md).
- [Vision](vision.md), [quyết định](monitoring.md), [cảnh báo ESP32](esp32-alerts.md).
- [Profile/model](models.md): mặc định serve và profile người dùng chọn có thể khác nhau.

## Kiểm tra

```bash
python -m unittest tests.test_runtime tests.test_evidence -v
```

Nếu sửa capture, kiểm thêm timestamp video, camera timeout và dừng worker.
Nếu sửa observer, so sánh cùng observation/video giữa run và serve; không báo parity bằng mắt nhìn.
