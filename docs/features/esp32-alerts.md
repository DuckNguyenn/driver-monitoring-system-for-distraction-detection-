# Cảnh báo ESP32 → buzzer

## Hợp đồng

Host yêu cầu USB serial 115200 baud, gửi `ALERT 1 <reasons>` hoặc `ALERT 0` và chờ `OK ALERT 1/0`.
Trong sketch tham khảo, lệnh hợp lệ làm mới watchdog; còi dùng GPIO25 và active HIGH.
Heartbeat host 500 ms; trạng thái suy luận cũ quá 250 ms không được giữ yêu cầu bật còi.
Sketch tham khảo tắt còi sau 2000 ms không nhận lệnh hợp lệ; host yêu cầu tắt khi shutdown bình thường.

## Công cụ nạp người dùng xác nhận ngày 28/10/2026

- Người dùng nạp bằng **ESP-IDF**, không dùng Arduino IDE. Lệnh build/flash/monitor ở [tổng hợp cách chạy](../../HUONG_DAN_CHAY_CHUONG_TRINH.md).
- Workspace hiện chứa `.ino` tham khảo; chưa tìm thấy source ESP-IDF khớp giao thức còi DA2 trong các thư mục đã rà. SDK ESP-IDF có trên máy không đồng nghĩa đã tìm được project firmware.
- Cần kiểm firmware IDF thật về UART/baud, phản hồi, watchdog và GPIO; không suy những thông số này chỉ từ `.ino`.
- Đóng IDF Monitor bằng Ctrl+] trước khi host mở serial; dừng host trước khi flash lại. Không tự tạo/chuyển hoặc nạp firmware chỉ vì cập nhật hướng dẫn.

## Ranh giới vận hành

- Cổng COM hoặc ttyUSB/ttyACM là serial ESP32; camera source là tham số khác.
- Mở USB có thể reset ESP32; host chờ boot rồi kiểm lại freshness trước gửi.
- ACK cũ không được xác nhận lệnh mới. Serial lỗi phải có trạng thái, retry và log rõ.
- Dashboard nhận trạng thái configured/unconfirmed/connected; chưa cấu hình không hiển thị đã nối.
- Cảnh báo tại chỗ không phụ thuộc việc điện thoại đang mở hoặc đường truyền Internet.
- Đấu driver còi theo tải/điện áp thực; tham khảo runbook phần cứng trước khi nạp.

## Thao tác và bằng chứng

[Nối dây, nạp và kiểm tra watchdog](../../esp32_buzzer/README.md).
Code và host simulator không đồng nghĩa đã nạp ESP32/đo còi trên Radxa.
Tại mốc hiện tại chưa có bằng chứng serial/còi thật của phiên bo này.

```bash
python -m unittest tests.test_alerting -v
```

Khi test phần cứng, ghi cổng thật, ACK, mất serial, ngừng host, watchdog và trạng thái tắt cuối.
ACK chỉ chứng minh firmware trả lời, không đo âm thanh thực tế hoặc thời gian phát còi.
