# Firmware còi ESP32 bằng ESP-IDF

Project ESP-IDF cho ESP32-WROOM-32, nhận quyết định từ PC/Radxa qua UART0.
AI không chạy trên ESP32. Bản `.ino` ở `esp32_buzzer/` được giữ làm tham khảo.

## Đối chiếu schematic

Đã đối chiếu với netlist của `ESP32_WROOM32_NATIVE.kicad_sch`, bản tham khảo
Chương 4 ngày 25/10/2026. Đây không phải xác nhận mạch đã lắp hoặc đã đo.

| Phần firmware | Net trong schematic | Kết nối |
|---|---|---|
| GPIO25, active HIGH | BUZZER_CTRL | U1 chân module 10 → R1 820 Ω → base Q1 BC337 |
| UART0 TX, GPIO1 | UART_TX | U1 chân 35 → J2 chân 1 |
| UART0 RX, GPIO3 | UART_RX | U1 chân 34 → J2 chân 2 |
| Mặc định LOW | Q1/R2 | R2 10 kΩ kéo base về GND, Q1 tắt |

Q1 đóng/ngắt phía âm của còi active BZ1; BZ1 dương nối 5 V, emitter Q1 nối GND.
U1 dùng 3,3 V và GND chung. Không cấp 5 V vào VDD hoặc RX/TX của module.
Diode D1: cathode phía 5 V, anode phía collector Q1.

Các số 10/34/35 là chân module WROOM, không phải số GPIO hay thứ tự chân devkit.
`main/board_config.h` tập trung cấu hình chân. Với còi passive cần thiết kế PWM riêng.

## Build và nạp

Mở ESP-IDF Terminal với SDK 5.5.x. Từ workspace DA2:

```powershell
Set-Location "C:\Users\P1 Gen 5\Downloads\DA2\esp32_buzzer_idf"
idf.py set-target esp32
idf.py build
idf.py -p COM5 flash monitor
```

`COM5` là ví dụ; kiểm tra cổng thật. Build tạo `build/driver_monitor_buzzer.bin`.
Chỉ chạy flash khi bo và dây đã sẵn sàng. Bản tạo trong lượt này chưa được nạp bo.

WROOM dạng module rời không có USB tích hợp: dùng USB–UART mức logic 3,3 V,
TX adapter → J2.2 (RX), RX adapter ← J2.1 (TX), GND chung. Schematic có RESET/BOOT
thủ công: giữ BOOT, nhấn/thả RESET, bắt đầu nạp rồi thả BOOT khi esptool kết nối.
Nếu dùng devkit có USB–UART thì dùng cổng USB của devkit.

Ứng dụng tắt console/log IDF để UART dành cho giao thức; ROM vẫn có thể in log lúc boot.
Thoát monitor bằng Ctrl+] trước khi Python mở cùng cổng COM. Dừng host trước khi nạp lại.

## Giao thức

115200 baud, 8 data bits, không parity, 1 stop bit, không flow control; kết thúc dòng LF hoặc CRLF.

```text
ALERT 1 eyes_closed_too_long
OK ALERT 1
ALERT 0
OK ALERT 0
```

- Mỗi lệnh hợp lệ làm mới timeout; `ALERT 1` không có reason cũng hợp lệ.
- Không nhận lệnh hợp lệ đủ 2000 ms khi đang bật: tắt và trả `FAULT COMMAND_TIMEOUT`.
- Vòng chờ UART kiểm tra timeout mỗi tick chờ 10 ms; thời điểm quan sát có độ trễ lịch FreeRTOS.
- Lệnh sai: `ERR UNKNOWN_COMMAND`; dòng quá 160 ký tự: `ERR TOO_LONG`; không làm mới timeout.
- Lỗi FIFO/buffer/frame/parity/break UART: tắt, trả `ERR UART_RX`, bỏ phần dòng lỗi đến LF kế tiếp.
- Khởi động luôn đặt GPIO LOW. Ngưỡng AI và heartbeat 500 ms vẫn do host quản lý.

## Kiểm tra

Từ DA2, không cần nối bo:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_esp32_idf tests.test_alerting -v
```

Test biên dịch lõi C thật bằng GCC, kiểm tra ACK, framing, timeout, tràn dòng,
byte NUL, lỗi UART, hồi phục và tràn bộ đếm thời gian. Không giả lập mạch điện.
Sau khi tự nạp bo và đóng monitor, kiểm tra ACK/bật-tắt ngắn:

```powershell
.\.venv\Scripts\python.exe tools/test_esp32.py --port COM5
```

Cần quan sát/đo thêm GPIO, âm thanh, dòng còi và mất liên lạc. ACK không chứng minh còi phát âm.

Nguồn API: [UART driver ESP-IDF 5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-reference/peripherals/uart.html).
