# Giám sát buồn ngủ — PC và Radxa ROCK 4D

Bản dùng chung chạy YuNet để tìm mặt/tâm mắt và hai YOLOv8n **classification** để phân loại mắt/ngáp. Logic cảnh báo dùng thời gian, nhận dữ liệu thiếu là `UNKNOWN`, điều khiển ESP32 và lưu nhật ký. Đã chạy ONNX trên PC/qua video và chuyển hai model nền sang RKNN cho RK3576. Trọng số PC hiệu chỉnh hiện tại chưa chuyển RKNN; suy luận NPU và nghiệm thu trên bo còn chờ Radxa được cài đặt.

Kết quả thực đo và giới hạn nằm trong [báo cáo triển khai](reports/IMPLEMENTATION_REPORT.md). [Hướng dẫn Radxa](DEPLOY_RADXA.md) và [thu video/gán nhãn](data_collection/README.md) là các bước tiếp theo.

Báo cáo kiến trúc model: [Word](reports/BAO_CAO_KIEN_TRUC_MODEL.docx), [PDF](reports/BAO_CAO_KIEN_TRUC_MODEL.pdf) và [Markdown](reports/BAO_CAO_KIEN_TRUC_MODEL.md). Báo cáo có sơ đồ, bảng từng tầng, số tham số kiểm kê trực tiếp từ checkpoint và phương án CPU/NPU trên ROCK 4D.

Báo cáo đồ án hiện tại: [Word](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.docx) và [PDF](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.pdf). Phần thiết kế mô tả camera → PC/Radxa → ESP32 → buzzer, kèm lý thuyết và 14 hình. Các mục chưa có phép đo vẫn để trống. Xem [cấu trúc thư mục](REPOSITORY_STRUCTURE.md) để phân biệt runtime, dữ liệu huấn luyện, model và hồ sơ kiểm thử.

## Chạy camera ngay trên Windows

Mở terminal tại thư mục dự án. Môi trường `.venv` và model ONNX đã chuẩn bị sẵn.

PowerShell:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display
```

CMD:

```bat
.venv\Scripts\python.exe -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display
```

Cũng có thể mở `scripts\start_camera.cmd`. Nhấn `Q`/`Esc` để thoát. CLI mặc định chạy không màn hình; `--display` mở cửa sổ xem kết quả.

Nếu cửa sổ hiện `UNKNOWN: blurry` dù đã tìm được mặt/mắt, thử profile PC đã tách ngưỡng độ nét mặt và mắt:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display
```

Profile này dùng ngưỡng mặt **20**, mắt **6** để thử với camera hiện tại, model mắt đã fine-tune trên vùng cắt thực tế và model ngáp đã hiệu chỉnh bằng video camera cùng dữ liệu cười; manifest đang dùng là `models/yawn_camera_refined/manifest.json`. Khi bỏ `min_eye_sharpness`, ngưỡng mắt lấy theo `min_sharpness` như cấu hình cũ. `Sharp face:giá_trị/ngưỡng eyes:giá_trị/ngưỡng` hiển thị số đo và ngưỡng tương ứng; `light` là độ sáng vùng mắt.

[Báo cáo sửa bỏ sót ngáp ngày 07/10/2026](reports/YAWN_CAMERA_FIX.md): trên video camera người dùng gửi, bản trước xác nhận 0/2 lần, bản mới xác nhận 2/2 và không tính cười thành ngáp. Giữ ngưỡng 0,70/1 giây, EMA 0,20 giây và kiểm tra chất lượng ảnh. Video một người được dùng cho hiệu chỉnh; lần ngáp thứ hai giữ lại sau chọn model, nhưng chưa phải kiểm thử độc lập theo người. Dùng `--config configs/camera_yawn_previous.yaml` để đối chiếu hoặc quay lại bản trước.

[Báo cáo sửa mắt mở bị nhận nhầm là nhắm](reports/EYE_CLASSIFIER_FIX.md) ghi dữ liệu bổ sung, kiểm thử nháy riêng một mắt, nhắm hai mắt thật và đối chiếu PyTorch/ONNX. Ca lỗi đã biết được thêm vào train; kết quả ảnh tĩnh chưa chứng minh độ chính xác trên camera của bạn. Thêm `--manifest models/smile_refined/manifest.json` để đối chiếu model mắt cũ và giữ model ngáp đã sửa. Trọng số mắt mới chưa có bản RKNN.

[Báo cáo sửa cười bị tính là ngáp](reports/SMILE_YAWN_FIX.md) ghi quy trình chọn model bằng validation và kiểm tra ảnh giữ riêng. Đây là model thử trên PC; chưa nghiệm thu video theo người hoặc NPU. Thêm `--manifest models/manifest.json` vào lệnh trên để đối chiếu model ban đầu với cùng ngưỡng camera. Cấu hình chung và RKNN gốc vẫn dùng model ban đầu.

Khung mắt hiển thị không có chữ R/L. `Eyes:both open` là hai mắt cùng mở, `Eyes:one closed` là một mắt nhắm và mắt kia mở với confidence đạt ngưỡng, `Eyes:both closed` là hai mắt cùng nhắm; kết quả chưa rõ giữ `unknown`. `Eyes P(closed)` hiển thị hai xác suất nhắm mắt; dấu `?` nghĩa là classifier chưa chạy trên vùng mắt đó. `Eye cycles total` cộng số lần đóng–mở của từng mắt, gồm cả nháy riêng một mắt hoặc đóng kéo dài. `Blink both` chỉ đếm chớp cả hai mắt có đoạn nhắm trùng nhau, kéo dài 0,05–0,5 s; `5s` là số chớp trong cửa sổ 5 giây, tổng đếm giữ theo tài xế hiện tại. Nháy riêng một mắt chỉ tăng `Eye cycles total`. Nhật ký vẫn giữ dữ liệu từng mắt để phân tích.

`Yawn P raw` là đầu ra classifier, `filtered` là xác suất dùng để quyết định. Profile PC thử bộ lọc EMA theo thời gian 0,20 s; cấu hình chung mặc định không lọc. `Yawn:confirm x/1s` là đang chờ xác nhận, `Yawn:yawn` là đã xác nhận một đợt. P gốc có thể biến động lúc bắt đầu/kết thúc ngáp. `UNKNOWN: uncertain_eyes` nghĩa là hai mắt chưa cùng đạt xác suất mở hoặc nhắm ≥0,8; mouth classifier hợp lệ vẫn được theo dõi, trong khi trạng thái tổng thể vẫn UNKNOWN và còi tắt.

Profile PC yêu cầu mắt mở chắc chắn liên tục 0,10 s để bắt đầu/kết thúc eye cycle. Nếu hình học mặt/mắt dịch chuyển khi đổi góc hoặc ngẩng đầu, runtime hiện `UNKNOWN: head_motion` và `Eyes:stabilizing ...s`, ngắt chuỗi eye cycle/blink/nhắm kéo dài, rồi chờ ổn định ít nhất 0,35 s. Model ngáp vẫn chạy nếu chất lượng mặt đạt. Các ngưỡng chuyển động là cấu hình thử; ca ảnh xoay không tăng chu kỳ sau sửa, nhưng chưa nghiệm thu recall trên video ngẩng đầu/chớp mắt tự nhiên. [Báo cáo lỗi eye cycle khi đổi góc](reports/EYE_MOTION_FIX.md) ghi kết quả và giới hạn.

[Bản sửa L/R, đóng–mở mắt và ngáp](reports/CAMERA_EVENT_FIXES.md) ghi kiểm thử và giới hạn. Nhấn `Q` để thoát phiên cũ rồi chạy lại lệnh trên sau khi cập nhật code.

[Kết quả chẩn đoán camera](reports/CAMERA_QUALITY_DIAGNOSIS.md) ghi số đo và giới hạn. Ngưỡng mắt 6 là cấu hình thử PC, cần hiệu chỉnh bằng video có nhãn trước khi dùng cho nghiệm thu cabin/Radxa. Nếu điểm độ nét mặt hoặc mắt vẫn dưới ngưỡng, kiểm tra lấy nét và chiếu sáng phía trước mặt. Thông số `fps: 0.0` của `probe_camera.py` là giá trị camera trả về; FPS xử lý thực nằm trong HUD và file summary.

Kiểm tra chỉ số camera:

```powershell
& '.\.venv\Scripts\python.exe' tools/probe_camera.py
```

Ở phiên kiểm tra ngày 06/10/2026, Windows nhận **Integrated Camera** và **Integrated IR Camera**; chỉ số `0` đọc được. Camera USB rời chưa được xác minh. Sau khi cắm USB, chạy lại công cụ và dùng chỉ số trả về frame. Đóng ứng dụng khác đang giữ camera. Đặt camera ngang, thấy trọn khuôn mặt và cả hai mắt. Nếu khung hình bị xoay, thêm `--rotate 90`, `180` hoặc `270`; đây là phép xoay toàn frame, không khôi phục khuôn mặt bị cắt khỏi ảnh.

Chạy 20 giây, không mở cửa sổ:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --headless --duration 20 --log-dir reports/camera_live
```

## Model có chạy trên video

Runtime đọc AVI/MP4 bằng OpenCV, dùng thời điểm của video để xác nhận nhắm mắt/ngáp. Tốc độ xử lý nhanh/chậm không làm thay đổi ngưỡng 1,5 giây.

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 'reports/video_fixture.avi' --backend onnx --display --realtime --log-dir reports/video_demo
```

Thay đường dẫn bằng video thật để kiểm tra. `--realtime` trình chiếu theo thời gian video; bỏ tùy chọn để xử lý offline nhanh nhất. `scripts\run_video.cmd "duong-dan-video.mp4"` cũng chạy được.

Phát lại video đã sửa lỗi ngáp bằng profile PC:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --config configs/camera_pc.yaml --source reports/yawn_camera_check/20261007T070644_475102Z.avi --backend onnx --display --realtime
```

`reports/video_fixture.avi` lặp lại ảnh mẫu bình thường/ngáp: đã đi qua detector, crop, cả hai classifier và logic thời gian. Đây là video kiểm tra kỹ thuật. Clip camera thật `reports/camera_recording.avi` có mặt bị cắt/lệch, nên replay trả `UNKNOWN`; chưa có video cabin được gán nhãn để đo recall sự kiện/báo nhầm.

Ghi một clip camera, không ghi đè file có sẵn:

```powershell
& '.\.venv\Scripts\python.exe' tools/record_camera.py --source 0 --seconds 30 --output data_collection/videos/p01_clip01.avi
```

Giữ file `.timestamps.json` cạnh AVI. AVI có FPS danh nghĩa 30; sidecar chứa thời gian lấy frame thật và runtime dùng sidecar để giữ cả khoảng mất frame. `--duration` giới hạn thời gian chạy thực; `--max-frames` giới hạn số frame xử lý.

## Trạng thái và cảnh báo

| Trạng thái | Ý nghĩa | Còi |
|---|---|---|
| `NORMAL` | Quan sát hợp lệ, chưa đủ bằng chứng cảnh báo; một đợt ngáp vẫn được ghi nhận | Tắt |
| `WARNING` | ≥2 đợt ngáp/60 s hoặc chớp mắt tăng | Tắt |
| `ALERT` | Hai mắt nhắm ≥1,5 s hoặc ngáp nhiều và chớp mắt tăng cùng lúc | Bật |
| `UNKNOWN` | Mất mặt, nhiều mặt trong ROI, quá tối/mờ, confidence thấp hoặc frame không còn hợp lệ | Tắt ngay, ngắt chuỗi xác nhận |

- Hai mắt đều `Closed ≥0,8` mới xác nhận nhắm; đều `Open ≥0,8` mới xác nhận mở. Kết quả khác giữ là chưa xác định.
- Ngáp bắt đầu sau `P(yawn) ≥0,70` liên tục 1 s; kết thúc sau `≤0,35` liên tục 0,5 s. Một đợt chỉ tính một lần.
- Chớp mắt là hai chuỗi đóng–mở 0,05–0,5 s có đoạn nhắm trùng nhau ≥0,05 s. Cho phép tối đa 0,15 s chuyển tiếp confidence chưa rõ để theo dõi chuỗi này; điều kiện nhắm kéo dài vẫn cần hai mắt ≥0,8 liên tục. Profile PC thêm xác nhận mở 0,10 s trước khi chốt sự kiện, nhưng đo thời lượng nhắm đến frame mở đầu tiên, không cộng thời gian chờ này. Chuyển động hình học ngắt chuỗi kênh mắt. So sánh hai cửa sổ 5 s đầy đủ của kênh mắt; cửa sổ hiện tại ≥4 lần và tăng ≥1 lần. Bộ đếm riêng từng mắt phục vụ quan sát.
- Khoảng frame >250 ms/ảnh cũ/chất lượng ảnh không đạt ngắt xác nhận. Mắt chưa rõ hoặc đang đổi góc/ngẩng đầu ngắt xác nhận nhắm kéo dài; ngáp vẫn được theo dõi khi phân phối mouth còn hợp lệ. Khi hết điều kiện kích hoạt, cần 1 s quan sát hợp lệ để tắt cảnh báo đang hồi phục. UNKNOWN tắt còi ngay.
- Thu lại cùng mặt sau mất quan sát ngắn giữ lịch sử sự kiện; vị trí mặt thay đổi lớn hoặc mặt trở nên nhập nhằng làm đặt lại lịch sử tài xế.

Ngưỡng, crop mắt `0,8d × 0,6d`, detector 320, ROI ghế lái và chất lượng ảnh nằm ở [configs/driver_monitor.yaml](configs/driver_monitor.yaml). Đường dẫn trong YAML tương đối với file YAML; đường dẫn trên CLI tương đối với thư mục terminal. Hiệu chỉnh bằng validation rồi giữ nguyên YAML/model trước test cuối. `driver_roi: [x1,y1,x2,y2]` dùng tọa độ 0–1 trên ảnh sau xoay.

## ESP32 và nhật ký

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --display --esp32-port COM7
```

`COM7` là ví dụ; dùng cổng thực của ESP32. [Firmware và sơ đồ nối dây](esp32_buzzer/README.md) quy định GPIO25, serial 115200, `ALERT 1 <reasons>`/`ALERT 0`, ACK và watchdog 2 s. Runtime gửi heartbeat 500 ms, thử kết nối lại khi lỗi và gửi tắt khi thoát. Nếu không truyền cổng, runtime vẫn nhận diện và ghi nhật ký.

Mỗi phiên sinh ba file trong `logs/` hoặc `--log-dir`:

- `*.csv`: từng frame, xác suất, chất lượng, trạng thái, số ngáp/chớp mắt, độ trễ và lỗi serial.
- `*.jsonl`: model/config/hashes khi bắt đầu, thay đổi trạng thái, thống kê mỗi giây, CPU/RAM/nhiệt độ khi đọc được, lỗi và kết thúc.
- `*.summary.json`: FPS, p95 độ trễ và số frame theo trạng thái. `accuracy: null` là chưa có ground truth, không phải độ chính xác bằng 0.

Camera chỉ giữ frame mới nhất. Video chạy tuần tự. P95 trong summary dùng histogram 1 ms, bin cuối ≥5000 ms; CSV giữ số đo gốc. FPS replay offline là tốc độ xử lý, cần đo lại bằng camera trên bo để nghiệm thu ≥15 FPS.

## Model, dependency và công cụ đánh giá

`models/manifest.json` chứa thứ tự lớp thực (`Closed, Open`; `no_yawn, yawn`), preprocessing RGB/resize cạnh ngắn/center crop 224, checksum và model của mỗi backend. Runtime kiểm tra checksum và đọc nhãn từ manifest. [Nguồn model](models/README.md) ghi phiên bản/checkpoint/YuNet.

Để tạo lại môi trường PC mới:

```powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-host.txt
& '.\.venv\Scripts\python.exe' -m pip check
```

`requirements-host.lock.txt` là snapshot toàn bộ dependency **Windows đã kiểm tra**, không dùng để cài Linux ARM64. Cấu hình Linux/SDK nằm riêng trong hướng dẫn Radxa.

Đánh giá ảnh và tương đương PyTorch→ONNX:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor parity --name eye --data kaggle_output/data/eye_dataset --output reports/eye_parity_new.json
& '.\.venv\Scripts\python.exe' -m driver_monitor parity --name yawn --data kaggle_output/data/yawn_dataset --crop face --output reports/yawn_crop_parity_new.json
```

Lệnh `evaluate-classifier` đánh giá một backend; `parity` thêm so sánh với `.pt`. Confidence/UNKNOWN ở lớp quyết định được báo riêng với F1 của classifier. Việc bỏ crop không dùng được khỏi mẫu sẽ làm kết quả quá lạc quan, nên evaluator tính chúng là mẫu bỏ sót.

Các dataset Kaggle bạn cung cấp là **ảnh tĩnh**. Các ảnh test cục bộ hiện chưa chứng minh việc tách theo người; F1 ảnh không thay thế recall sự kiện trên video. Công cụ `prepare-dataset`, `train`, `evaluate-session` và `evaluate-study` cùng mẫu CSV được hướng dẫn trong [quy trình dữ liệu](data_collection/README.md).

Kiểm thử phần mềm:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '.\.venv\Scripts\python.exe' -m unittest discover -s camera_classical/tests -v
```

Bản Haar/FaceMesh/EAR/MAR ở `camera_classical/` giữ để đối chiếu trên PC, dùng chung bộ quyết định thời gian. Bản chính triển khai trên bo là `python -m driver_monitor`; không cần MediaPipe. Các tài liệu/đồ án cũ và DOCX tham khảo là bối cảnh, còn báo cáo triển khai mới phản ánh chức năng thực tế của bản này.
