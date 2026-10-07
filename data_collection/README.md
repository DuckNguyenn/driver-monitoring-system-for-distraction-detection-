# Dữ liệu video, crop và kiểm thử độc lập

Dataset ảnh Kaggle đang có phù hợp để kiểm tra classifier: [Eyes dataset](https://www.kaggle.com/datasets/charunisa/eyes-dataset), [MRL eye dataset](https://www.kaggle.com/datasets/tauilabdelilah/mrl-eye-dataset), [Yawning dataset](https://www.kaggle.com/datasets/deepankarvarma/yawning-dataset-classification). Chưa có video cabin có nhãn/tách người; không thể từ ảnh tĩnh suy ra recall nhắm mắt kéo dài hay số báo nhầm mỗi giờ.

## Thu dữ liệu

Thu tối thiểu 5 người trong cabin đủ sáng, xe dừng; cố định camera/ROI như vị trí triển khai. Giữ ít nhất 2 người chỉ dùng cho test. Tách theo **người** trước, rồi theo clip; mọi ảnh/video của một người chỉ thuộc một split.

Test cuối cần ≥30 sự kiện hai mắt nhắm kéo dài ≥1,5 s, ≥30 đợt ngáp và ≥2 giờ hoạt động bình thường. Có nói chuyện, cười, kính, quay đầu và mặt bị che. Ghi điều kiện ánh sáng trong mọi clip. Thu cả đoạn chất lượng không đạt để đánh giá `UNKNOWN`.

Tạo thư mục `data_collection/videos/`, ghi AVI kèm sidecar bằng `tools/record_camera.py` hoặc dùng MP4 có timestamp/FPS hợp lệ. Kiểm tra video thấy trọn mặt trước khi thu dài. Giữ `*.timestamps.json` cạnh clip của công cụ ghi.

## Gán nhãn

Sao chép `annotations.template.csv` thành `annotations.csv`, điền nhãn bằng cách xem video thật. `start/end` là giây từ frame đầu, theo thời gian sidecar nếu có; **không** suy ra nhãn từ dự đoán AI.

```csv
subject_id,clip_id,split,lighting,start,end,label
p01,p01_clip01.avi,train,daylight,0,4,normal
p01,p01_clip01.avi,train,daylight,4,6.2,eyes_closed
p01,p01_clip01.avi,train,daylight,6.2,10,normal
p01,p01_clip01.avi,train,daylight,10,12.5,yawn
p01,p01_clip01.avi,train,daylight,12.5,15,unknown
```

Đây là ví dụ định dạng, không phải dữ liệu nghiệm thu. Nhãn `normal` nghĩa hai mắt mở, không ngáp; `eyes_closed` ghi đúng bắt đầu/kết thúc hai mắt đóng; `yawn` ghi cả đợt; `unknown` cho đoạn không xác định. Mắt nhắm và ngáp có thể đồng thời, nhưng nhãn bình thường/không rõ không chồng với sự kiện đã xác định. Clip và người phải giữ split/ánh sáng nhất quán. Dùng clip_id là đường dẫn tương đối trong thư mục video.

Với AVI có sidecar, xem bằng `driver_monitor run --source ... --display --realtime`: giá trị `t:...s` hiển thị thời gian thật. Timestamp của trình xem AVI thông thường có thể khác vì header FPS danh nghĩa; không chép timestamp đó vào nhãn của sidecar.

## Tạo crop đúng pipeline và fine-tune khi cần

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor prepare-dataset --annotations data_collection/annotations.csv --videos data_collection/videos --output data_collection/crops
```

Công cụ lấy tối đa khoảng 5 frame/s, dùng đúng YuNet/crop/rotation/quality như runtime. Nhãn ngáp không tự tạo nhãn mắt mở; nhãn mắt nhắm không tự tạo nhãn không ngáp. Bỏ đoạn không có nhãn/UNKNOWN/crop kém, lưu người/clip/split/hash của mỗi crop trong manifest. Thư mục output phải mới để tránh trộn các lần xử lý.

Calibration chỉ tạo từ split `train`, với preprocessing RGB/224 tương đương runtime. File `eye.calibration.json`, `yawn.calibration.json` dùng cho converter INT8; test không tham gia calibration.

Nếu validation chưa đạt mục tiêu:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor train --name eye --data data_collection/crops --checkpoint camera_classical/best_eye.pt --output training --epochs 40
& '.\.venv\Scripts\python.exe' -m driver_monitor train --name yawn --data data_collection/crops --checkpoint camera_classical/best_yawn.pt --output training --epochs 40
```

Training kiểm tra có cả hai lớp ở train/val/test, không trùng người hoặc hash qua split. Nó không tự thay checkpoint triển khai. Chọn model/ngưỡng bằng validation, xuất model mới, khóa config/hashes, rồi đánh giá test cuối một lần. Bộ crop chuẩn bị cần bổ sung đầy đủ lớp cho từng split trước khi train.

## Đánh giá ảnh và sự kiện

F1 ảnh trên crop độc lập:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor evaluate-classifier --name eye --data data_collection/crops/eye --output reports/eye_independent.json
& '.\.venv\Scripts\python.exe' -m driver_monitor evaluate-classifier --name yawn --data data_collection/crops/yawn --output reports/yawn_independent.json
```

Replay mỗi clip test bằng config/model đã khóa:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source data_collection/videos/p04_clip01.avi --backend onnx --headless --log-dir reports/clip_replays
```

Sau replay, dùng tên CSV được sinh ra; thay `SESSION` bằng tên phiên thực:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor evaluate-session --frames reports/clip_replays/SESSION.csv --annotations data_collection/annotations.csv --clip-id p04_clip01.avi --output reports/clip_metrics/p04_clip01.json
& '.\.venv\Scripts\python.exe' -m driver_monitor evaluate-study --reports reports/clip_metrics --annotations data_collection/annotations.csv --output reports/study.json
```

Giữ JSONL cạnh CSV để kiểm tra source/config. Evaluator từ chối timestamp đảo, nhãn vượt phạm vi log, clip không khớp và config/model khác phiên replay. Chỉ xác nhận sự kiện riêng biệt; một trạng thái ngáp kéo dài không được tính trúng nhiều nhãn. Reaction đo ở quyết định; cần đo thêm còi vật lý trên ESP32.

Tổng hợp test theo số sự kiện và thời gian bình thường thực, không trung bình đơn giản các phần trăm. Báo cáo theo người/ánh sáng, số đoạn chưa đánh giá và tỉ lệ `UNKNOWN`. `event_criteria_met` chỉ là tiêu chí recall/báo nhầm khi đủ dữ liệu; F1 độc lập, chuyển RKNN, tốc độ bo, còi và chạy 2 giờ vẫn cần bằng chứng riêng.
