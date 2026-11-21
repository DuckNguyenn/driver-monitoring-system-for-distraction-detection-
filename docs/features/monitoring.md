# Quyết định theo thời gian

## Hợp đồng

`Observation` → `Monitor.update` → `Status`. Logic thuần không phụ thuộc camera, NumPy hay serial.
Giữ bốn trạng thái NORMAL, WARNING, ALERT, UNKNOWN và nguyên nhân có thể kiểm tra.
Nguồn thật của tham số là MonitorConfig và YAML đang chọn; con số dưới đây là profile hiện dùng.

## Mắt và sự kiện

- Hai mắt cùng Closed ≥0,8 liên tục 1,5 giây xác nhận mắt nhắm kéo dài.
- Hai mắt cùng Open ≥0,8 xác nhận mở; phân phối thiếu/không hợp lệ/chưa chắc giữ trạng thái chưa xác định.
- Eye cycle một mắt là thông tin chẩn đoán. Blink chỉ ghép hai chu kỳ ngắn, chồng thời gian,
  trong khoảng 0,05–0,5 giây. Nháy một mắt không tự tăng blink hai mắt.
- Profile near/medium có xác nhận mở 0,1 giây trước khi kết thúc chu kỳ.
- So sánh hai cửa sổ blink 5 giây hoàn chỉnh; hiện tại ≥4 lần và tăng ≥1 lần.

## Ngáp và cảnh báo

- Yawn vào đợt khi P ≥0,70 đủ 1 giây; ra đợt khi P ≤0,35 đủ 0,5 giây.
- Mỗi đợt tính một lần. Profile near/medium có EMA 0,2 giây; log giữ raw và filtered.
- Profile thử nghiệm DV20 cho hội thoại dùng model đa góc, EMA 0,2 giây và yêu cầu
  P đã lọc ≥0,65 liên tục 2 giây hoặc ≥0,75 liên tục 1,4 giây. Hai điều kiện dùng chung bộ đếm.
  Model vẫn chỉ phân loại ngáp qua ảnh. Chưa đánh giá tình huống điện thoại che miệng.
  Khi phát lại ở tốc độ lấy mẫu gốc, hai clip nói chuyện `04_talking` và `05_head_turn`
  giảm từ 2 và 1 sự kiện xuống 0; `01_yawn_clear` vẫn ghi 1 sự kiện. Đây là clip hiệu chỉnh.
  Gói chạy riêng trên Radxa nằm ở `dist/DA2-dv20-speech.zip`.
- Một lần ngáp chỉ ghi lịch sử; nhiều ngáp hoặc blink tăng tạo WARNING.
- ALERT kết hợp các bằng chứng theo Monitor; client không tự tái tính từ biểu đồ.
- Gap >250 ms, timestamp đảo/frame cũ hoặc quan sát không hợp lệ ngắt chuỗi xác nhận.
- Dữ liệu thiếu không được trở thành False/0. UNKNOWN tắt điều kiện alert đang thiếu bằng chứng;
  recovery theo khoảng quan sát hợp lệ và config.

## Kiểm tra bắt buộc khi sửa

```bash
python -m unittest tests.test_monitor tests.test_camera_events -v
```

Bao phủ FPS biến đổi, timestamp đảo, frame cũ/gap, confidence thấp, wink, hai mắt nhắm lâu,
một/hai đợt ngáp, recovery và đổi nhánh model mắt. Xem [thuật ngữ](../../CONTEXT.md).
