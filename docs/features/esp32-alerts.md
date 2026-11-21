# Cảnh báo ESP32 → buzzer

## Hợp đồng

Host yêu cầu USB serial 115200 baud, gửi `ALERT 1 <reasons>` hoặc `ALERT 0` và chờ `OK ALERT 1/0`.
Firmware [ESP-IDF](../../esp32_buzzer_idf/README.md): UART0 TX GPIO1/RX GPIO3; còi GPIO25 active HIGH.
Heartbeat host 500 ms; trạng thái suy luận cũ quá 250 ms không được giữ yêu cầu bật còi.
Lệnh hợp lệ làm mới timeout; firmware tắt sau 2000 ms không có lệnh hợp lệ (độ trễ lịch vòng chờ 10 ms).
Lỗi UART làm tắt còi và hủy phần dòng lỗi; host yêu cầu tắt khi shutdown bình thường.

## Công cụ nạp người dùng xác nhận ngày 28/10/2026

- Người dùng nạp bằng **ESP-IDF**, không dùng Arduino IDE. Lệnh build/flash/monitor ở [tổng hợp cách chạy](../../HUONG_DAN_CHAY_CHUONG_TRINH.md).
- Đã tạo `esp32_buzzer_idf/` theo yêu cầu mới; `.ino` cũ giữ tham khảo, không phải firmware IDF.
- Chân và mức điều khiển đã đối chiếu netlist `ESP32_WROOM32_NATIVE` tham khảo Chương 4: GPIO25 → R1 → Q1 BC337 → còi active 5 V; UART0 nối J2.
- Đóng IDF Monitor bằng Ctrl+] trước khi host mở serial; dừng host trước khi flash lại. Tạo/build không đồng nghĩa đã nạp bo.

## Ranh giới vận hành

Ngày 13/11: extension VS Code ESP-IDF 2.3.0 tự dò cổng lỗi với tên chip `ESP32-D0WD-V3`.
Parser trong extension bỏ dấu `-` rồi so sánh toàn bộ tên chip với target `esp32`, nên loại COM5.
Replay trực tiếp parser đã tái hiện: tên đầy đủ trả null, tên `ESP32` trả COM5.
Đã đặt `idf.port: COM5` trong settings cục bộ của DA2 và project IDF để bỏ qua tự dò.
Log người dùng sau đó xác nhận boot và kiểm tra ACK qua COM5 thành công; chưa đo còi/watchdog.
Nếu còn lỗi, dùng ESP-IDF Terminal: `idf.py -p COM5 flash` tại `esp32_buzzer_idf/`.

- Cổng COM hoặc ttyUSB/ttyACM là serial ESP32; camera source là tham số khác.
- Mở USB có thể reset ESP32; host chờ boot rồi kiểm lại freshness trước gửi.
- ACK cũ không được xác nhận lệnh mới. Serial lỗi phải có trạng thái, retry và log rõ.
- Dashboard nhận trạng thái configured/unconfirmed/connected; chưa cấu hình không hiển thị đã nối.
- Cảnh báo tại chỗ không phụ thuộc việc điện thoại đang mở hoặc đường truyền Internet.
- Đấu driver còi theo tải/điện áp thực; tham khảo runbook phần cứng trước khi nạp.

## Thao tác và bằng chứng

[Nối dây, nạp và kiểm tra watchdog](../../esp32_buzzer/README.md).
Code và host simulator không đồng nghĩa đã nạp ESP32/đo còi trên Radxa.
Ngày 13/11, người dùng chạy `python tools/test_esp32.py --port COM5` và gửi `ACK test passed`.
Đây là bằng chứng giao thức từ terminal người dùng, không phải quan sát phần cứng trực tiếp của agent.
Giá trị in `ALERT 1 ACK latency: 0.0 ms` chưa đủ để kết luận độ trễ thực bằng không.
Âm thanh còi, thử rút USB và watchdog 2 giây chưa được xác nhận.
Build ESP-IDF 5.5.4 và 24 test firmware/host/docs đã đạt; [bằng chứng](../evidence/2026-10-28-esp-idf.json).

```bash
python -m unittest tests.test_alerting -v
python -m unittest tests.test_esp32_idf -v
```

Khi test phần cứng, ghi cổng thật, ACK, mất serial, ngừng host, watchdog và trạng thái tắt cuối.
ACK chỉ chứng minh firmware trả lời, không đo âm thanh thực tế hoặc thời gian phát còi.
