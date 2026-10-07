# ESP32 WROOM — còi và watchdog

Firmware `esp32_buzzer.ino` nhận lệnh ASCII qua USB serial 115200 baud. GPIO25 điều khiển còi active ở mức HIGH; nếu bo/còi của bạn khác, sửa `BUZZER_PIN` hoặc mức active theo phần cứng thực.

| Kết nối | Đích |
|---|---|
| USB PC/Radxa | Cổng USB ESP32, vừa cấp nguồn vừa truyền serial |
| GPIO25 ESP32 | IN của module còi active có mạch driver tương thích 3,3 V |
| GND ESP32 | GND module còi |
| Nguồn module | Theo điện áp định mức của module, GND chung |

Còi rời cần transistor/MOSFET hoặc module driver theo dòng tải; GPIO chỉ cấp tín hiệu điều khiển. Còi passive cần PWM và không phù hợp với sketch HIGH/LOW hiện tại. Nạp sketch bằng Arduino IDE, chọn đúng ESP32/cổng USB thực.

```text
ALERT 1 eyes_closed_too_long
OK ALERT 1
ALERT 0
OK ALERT 0
```

`ALERT 1` không kèm reason cũng hợp lệ. Reason chỉ giải thích ở host; firmware không tự nhận diện. Lệnh sai trả `ERR UNKNOWN_COMMAND`; dòng quá 160 ký tự bị bỏ và trả `ERR TOO_LONG`. ACK chỉ được gửi cho lệnh hợp lệ. Mỗi lệnh hợp lệ làm mới watchdog; không nhận lệnh trong 2000 ms khi còi bật sẽ tắt và báo `FAULT COMMAND_TIMEOUT`.

Runtime có heartbeat 500 ms và ngắt còi khi suy luận thiếu kết quả mới >250 ms. Lỗi serial được ghi log/thử lại sau 1 s. Cổng USB có thể reset ESP32 khi mở nên host chờ boot, rồi kiểm tra lại độ mới của trạng thái trước khi gửi.

Kiểm tra trên bàn sau khi nạp:

```powershell
& '.\.venv\Scripts\python.exe' tools/test_esp32.py --port COM7
```

`COM7` là ví dụ; Linux dùng `/dev/ttyUSB0`, `/dev/ttyACM0` hoặc by-id tương ứng. Công cụ thử ACK/bật ngắn/tắt, tắt trong `finally`, đo thời gian ACK. ACK không đo thời điểm còi thực phát âm.

Để kiểm tra mất liên lạc, gửi `ALERT 1` rồi dừng gửi lệnh nhưng giữ nguồn ESP32, đo GPIO/còi tắt ≤2 s; sau đó kiểm tra dừng process/rút serial/kết nối lại. Gửi `ALERT 0` khi kết thúc. Không đưa kết quả mô phỏng thành kết quả phần cứng.

Kiểm thử host C++ `tools/firmware_test.cpp` biên dịch trực tiếp sketch với I/O giả, đã kiểm tra startup, ACK, heartbeat, watchdog, lệnh sai, tràn dòng và rollover millis. Sketch chưa được cross-compile/nạp lên ESP32 trong phiên này.
