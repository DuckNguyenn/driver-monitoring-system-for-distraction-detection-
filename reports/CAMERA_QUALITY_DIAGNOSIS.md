# Chẩn đoán `UNKNOWN: blurry` trên camera PC

Ngày kiểm tra: 06/10/2026. Backend ONNX, camera số 0, 640×480.

Số liệu dưới đây được đo trước bản sửa L/R và logic sự kiện. HUD, bộ đếm từng mắt và việc theo dõi ngáp khi mắt chưa rõ đã được cập nhật tiếp trong [báo cáo sửa sự kiện](CAMERA_EVENT_FIXES.md).

## Nguyên nhân trong nhật ký

Phiên `20261006T122039_722946Z` có 733 frame: 728 `blurry`, 3 đạt chất lượng và 2 không tìm thấy mặt. Trong 3 frame đạt chất lượng, 2 trả `NORMAL`, 1 trả `UNKNOWN: uncertain_eyes`.

53 bản ghi JSONL có đủ số đo chất lượng: trung vị độ nét vùng mặt 30,48, vùng mắt thấp nhất 7,89. Code cũ dùng ngưỡng 20 cho cả hai vùng. Khi mắt dưới ngưỡng, runtime bỏ qua cả hai classifier và giữ quan sát `UNKNOWN`. Bbox xanh cho thấy YuNet đã tìm được vùng crop, chưa chứng minh classifier đã chạy.

Đã bổ sung `min_eye_sharpness` độc lập với `min_sharpness`. Khi không đặt ngưỡng riêng, mắt vẫn dùng ngưỡng chung của cấu hình cũ. Profile [camera_pc.yaml](../configs/camera_pc.yaml) dùng ngưỡng mặt 20, mắt 6; các điều kiện quá tối, quá sáng và confidence ≥0,8 vẫn được kiểm tra. Đây là cấu hình thử cho PC, chưa được xác nhận bằng nhãn độc lập.

## Kết quả kiểm tra

Áp dụng lại bước kiểm tra chất lượng trên **cùng 53 bản ghi số đo cũ**:

| Ngưỡng mặt / mắt | Đạt chất lượng | Bị chặn vì mờ |
|---|---:|---:|
| 20 / 20 | 2 | 51 |
| 20 / 6 | 46 | 7 |

Replay này chỉ kiểm tra điều kiện chất lượng. Nhật ký không lưu ảnh gốc, nên không suy luận lại classifier và không đo độ chính xác hoặc khả năng cảnh báo từ bảng này. 53 mẫu có số đo là các bản ghi khi đổi trạng thái/thống kê; không đại diện đầy đủ cho 733 frame.

Phiên **camera thật sau sửa** `20261006T123514_244359Z` dùng profile PC:

| Chỉ số | Số đo |
|---|---:|
| Thời gian chạy | 12,015 s |
| Frame xử lý | 176 |
| Frame đạt chất lượng, chạy classifier | 173 |
| `NORMAL` | 135 |
| `UNKNOWN: uncertain_eyes` | 38 |
| `UNKNOWN: blurry` | 3 |
| FPS thực | 14,65 |
| Độ trễ từ lấy frame tới quyết định p95 | 32 ms |
| Lỗi runtime | Không |

Hai phiên camera diễn ra ở thời điểm khác nhau, có chất lượng ảnh khác nhau; bảng camera thật không phải thí nghiệm so sánh độ chính xác trước/sau. Chưa có ground truth để khẳng định trạng thái nhận diện đúng. FPS đo được còn dưới mục tiêu 15 FPS; đây là số đo PC, chưa phải nghiệm thu Radxa.

35/35 test của runtime dùng chung đã đạt. Test hồi quy tái hiện đúng đường đi `Vision.observe`, kiểm tra ngưỡng riêng cho mắt, khả năng dùng lại cấu hình cũ, chặn mặt/mắt dưới ngưỡng, ảnh tối/cháy sáng và từ chối ngưỡng không hợp lệ. Test tái hiện đã thất bại trước sửa và đạt sau sửa.

Phần hiển thị mới đã chạy với YuNet và hai model ONNX thật trên một frame của `video_fixture.avi`; ảnh [xem thử HUD](../report_assets/camera_pc_hud.png) lấy từ video kiểm tra đó. Phiên camera 12 giây ở bảng trên chạy không mở cửa sổ và chỉ lưu nhật ký.

## Chạy và đọc màn hình

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display
```

`Sharp face:30.5/20 eyes:7.9/6` hiển thị số đo và ngưỡng tương ứng. `Eye P(Closed)` là xác suất nhắm của từng mắt; dấu `?` ở dòng này nghĩa là chưa chạy classifier trên frame đó. `UNKNOWN: uncertain_eyes` vẫn là dữ liệu chưa đủ xác nhận: hai mắt phải cùng có `Closed ≥0,8` hoặc cùng có `Open ≥0,8`. Xác suất ngáp trong trạng thái quyết định/CSV có thể để trống khi quan sát chưa đủ xác nhận; JSONL vẫn lưu phân phối ngáp gốc trong `observation.yawn` nếu classifier đã chạy. Quan sát mở mắt/nhắm mắt/ngáp và gán nhãn clip để kiểm tra trước khi khóa ngưỡng cho cabin.

Windows hiện liệt kê **Integrated Camera** và **Integrated IR Camera**. Camera USB rời chưa được xác minh. `probe_camera.py` đọc được camera số 0; cảnh báo cho số 1–3 phản ánh các chỉ số đó không mở được. Giá trị `fps: 0.0` trong probe là thông số trả về từ camera; file summary có FPS thực tính theo số frame và thời gian chạy.

Số liệu gốc và thống kê: [JSON chẩn đoán](camera_quality_diagnosis.json), [summary camera mới](camera_pc_check/20261006T123514_244359Z.summary.json), [test hồi quy](../tests/test_camera_quality.py).

Lần thử trong sandbox không mở được camera và đã ghi lỗi khởi động rõ ràng. Phiên có số đo 176 frame là lần chạy lại được cấp quyền truy cập camera ngoài sandbox.
