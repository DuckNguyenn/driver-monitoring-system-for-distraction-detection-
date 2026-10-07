# Sửa nhãn mắt, bộ đếm đóng–mở và theo dõi ngáp

Ngày 06/10/2026. Người dùng xác nhận đang nháy riêng một mắt và P(ngáp) 0,4–0,9 biến động trong lúc thực hiện ngáp.

## Nguyên nhân đã tái hiện

1. YuNet trả landmark mắt phải trước mắt trái. Runtime trước đây giữ nguyên thứ tự đó nhưng đặt tên phần tử đầu là mắt trái. [Tài liệu OpenCV 4.11](https://docs.opencv.org/4.11.0/df/d20/classcv_1_1FaceDetectorYN.html#details) ghi vị trí 4–5 cho mắt phải, 6–7 cho mắt trái. Bản sửa trả crop theo thứ tự mắt trái tài xế, mắt phải tài xế, mặt.
2. Bộ đếm cũ là số chớp hai mắt trong 5 giây; nháy riêng một mắt không tăng số đó. Frame chuyển tiếp confidence chưa rõ còn làm mất chuỗi đóng–mở đang xác nhận. Test 15 FPS với Open → chưa rõ → Closed → chưa rõ → Open đã trả 0 trước sửa và 1 sau sửa.
3. `uncertain_eyes` từng ngắt cả logic ngáp và để trống P ngáp ở trạng thái quyết định/CSV dù classifier đã chạy. Test với hai mắt chưa rõ và P(ngáp)=0,9 liên tục 1,2 s đã tái hiện việc mất P và bỏ sự kiện. Sau sửa vẫn giữ trạng thái tổng thể UNKNOWN/còi tắt, nhưng ghi nhận một đợt ngáp và giữ xác suất của kênh mouth.

Trong phiên người dùng `logs/20261006T124238_059329Z.jsonl` (2539 frame/169,75 s), 165 **bản ghi lấy mẫu** có P ngáp gốc >0,7; 86 bản ghi đi kèm `uncertain_eyes`. Đây là bằng chứng kênh mắt đang cản việc xử lý ngáp, chưa phải số ngáp đúng/sai. JSONL cũ lấy mẫu theo đổi trạng thái/mỗi giây nên không được dùng làm video liên tục để tính recall.

## Hành vi mới

- L/R theo bên mắt của tài xế, được ghi ngay trên hai bbox và dòng `Driver L/R`.
- `Eye cycles L/R` tăng khi từng mắt hoàn thành mở → nhắm → mở với thời gian nhắm ≥0,05 s. Đóng kéo dài cũng tăng bộ đếm riêng khi mở lại. Nháy riêng trái tăng L; nháy riêng phải tăng R. Số này dùng để quan sát thao tác từng mắt.
- `Blink both` tính chuỗi đóng–mở của cả hai mắt, mỗi mắt nhắm 0,05–0,5 s, có đoạn nhắm trùng nhau ≥0,05 s. Chỉ các sự kiện này tham gia tần suất chớp/cảnh báo. Tổng đếm giữ theo tài xế hiện tại; số `5s` tự giảm khi sự kiện hết cửa sổ.
- Theo dõi sự kiện mắt cho phép chuyển tiếp chưa rõ trong tối đa 0,15 s kể từ lần mắt đó có confidence đủ xác nhận. Mất mặt, ảnh kém, frame cũ hoặc gap lớn ngắt chuỗi. Bộ xác nhận nhắm kéo dài vẫn ngắt ngay khi một mắt chưa đủ confidence; hai mắt phải cùng Closed ≥0,8 liên tục 1,5 s mới kích hoạt điều kiện này.
- Kênh mouth hợp lệ được xử lý độc lập với confidence của mắt. Trạng thái tổng thể UNKNOWN vẫn tắt còi ngay. Lỗi chất lượng/frame ngắt cả hai kênh.
- `Yawn P raw` giữ đầu ra classifier; `filtered` là đầu vào quyết định sau EMA. [Profile PC](../configs/camera_pc.yaml) thử hằng số thời gian 0,20 s, tính theo timestamp để tránh phụ thuộc FPS. Mặc định `yawn_smoothing_seconds: 0.0` giữ xác suất chưa lọc ở cấu hình chung.
- Ngáp vẫn cần xác suất quyết định ≥0,70 liên tục 1 s, và ≤0,35 liên tục 0,5 s để kết thúc. `Yawn:confirm x/1s` hiển thị giai đoạn xác nhận; sau xác nhận, P dao động 0,4–0,9 không tự kết thúc hoặc tăng lại cùng một đợt.
- CSV ghi P gốc/P quyết định, thời gian xác nhận, tổng chớp hai mắt và bộ đếm riêng L/R. JSONL ghi thêm khi các bộ đếm hoặc trạng thái ngáp đổi, cùng `eye_order: driver_anatomical_left_right` trong metadata phiên.

## Kiểm thử thực hiện

**48/48 test runtime chung và 2/2 test tương thích PC đạt.** Ba test tái hiện đã thất bại trước sửa. Các test mới bao phủ nháy riêng trái, đóng riêng một mắt kéo dài, chớp hai mắt hơi lệch thời điểm, confidence chưa rõ kéo dài, mất chất lượng/frame cũ/gap, đổi tài xế, nhắm dài bị ngắt khi confidence giảm, spike ngáp, P ngáp dao động sau xác nhận và thời gian lọc ở 5/15/30/60 FPS.

| Chạy kiểm tra | Kết quả |
|---|---|
| Video fixture, ONNX, profile PC | 135 frame, đọc hết clip, xác nhận 1 đợt ngáp, 0 frame bật còi, không lỗi runtime |
| HUD với detector/classifier thật | Vẽ và xử lý đủ 135 frame của fixture; kiểm tra trực quan [mẫu bình thường](../report_assets/camera_events_hud_normal.png) và [mẫu ngáp](../report_assets/camera_events_hud_yawn.png) |
| Camera thật, nguồn 0, chạy không mở cửa sổ | 147 frame/10,016 s; 14,68 FPS; p95 đọc→quyết định 33 ms; không lỗi runtime |
| Quan sát camera | 147 frame đạt chất lượng; NORMAL 113, UNKNOWN do mắt chưa rõ 34; P ngáp gốc được lưu đủ 147 frame, P quyết định vẫn hiện ở 34 frame mắt chưa rõ |

Các bộ đếm trong phiên camera ghi tối đa Blink both=1, Eye cycles L=3/R=2, yawn_count=1. Camera chưa có nhãn đối chiếu; đây là bằng chứng phần mềm vận hành và ghi số đếm, chưa chứng minh các sự kiện đó đúng. FPS PC đo được vẫn dưới mục tiêu 15 FPS của nghiệm thu pipeline trên bo.

Fixture ghép ảnh tĩnh làm phép kiểm tra decoder→YuNet→crop→classifier→logic→HUD; không mô phỏng đầy đủ chuyển động ngáp. Bộ lọc làm giảm biến động theo thời gian, nhưng không sửa nhãn sai từ classifier. Hai checkpoint/preprocessing classifier giữ nguyên; chưa fine-tune hoặc đo lại F1 trên video có nhãn. Để đánh giá việc cải thiện nhận diện, cần clip ngáp thật cùng đoạn bình thường/nói chuyện/cười và nhãn độc lập theo [quy trình dữ liệu](../data_collection/README.md).

## Chạy lại

Nhấn Q hoặc Esc để thoát phiên cũ, rồi chạy:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display
```

Nháy trái rồi mở lại để kiểm tra L tăng; nháy phải rồi mở lại để kiểm tra R tăng; chớp cả hai để kiểm tra `Blink both`. Khi ngáp, theo dõi `raw`, `filtered`, `confirm` và `yawns` cùng nhau. Một đợt chỉ tăng `yawns` một lần. Ngưỡng mắt 6 và EMA 0,20 s của profile PC cần được hiệu chỉnh bằng validation có nhãn trước nghiệm thu.

Nhật ký mới: [camera summary](events_camera_check/20261006T130820_201090Z.summary.json), CSV/JSONL cùng tên; [video summary](events_video_check/20261006T130656_602467Z.summary.json). [Test sự kiện](../tests/test_camera_events.py) và [test thứ tự crop](../tests/test_models_vision.py) chứa các tình huống tái hiện.
