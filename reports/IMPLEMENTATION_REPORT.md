# Báo cáo triển khai và kiểm thử — 06/10/2026

Đã triển khai bản dùng chung cho PC và Radxa: YuNet + hai classifier, quyết định theo thời gian, camera/video, ONNX/RKNN adapter, ESP32, nhật ký và công cụ đánh giá. **Đã kiểm thử PC; chưa nghiệm thu Radxa/NPU hoặc độ chính xác cảnh báo trên video cabin độc lập.** Bo chưa được setup theo thông tin người dùng. Tài liệu DOCX tham khảo và báo cáo đồ án cũ không được dùng làm bằng chứng đã đạt tính năng/hiệu năng.

## 1. Cấu hình thực đã xác minh

- Windows 11 AMD64, Python 3.12.10, RAM 16.871.448.576 byte theo [preflight](preflight_pc.json).
- Torch 2.6.0, torchvision 0.21.0, Ultralytics 8.4.163, ONNX 1.17.0, ONNX Runtime 1.20.1, OpenCV 4.11.0.86, NumPy 1.26.4. `pip check` đạt; snapshot toàn bộ dependency ở `../requirements-host.lock.txt`.
- Checkpoint thực là **YOLOv8n classification 224×224**, mắt `[Closed, Open]`, ngáp `[no_yawn, yawn]`. Manifest giữ class/preprocessing/hash; đã sửa giả định thứ tự lớp bị đảo ở luồng chuyển model cũ.
- YuNet `face_detection_yunet_2023mar.onnx`, commit OpenCV Zoo `47534e27c9851bb1128ccc0102f1145e27f23f98`, SHA256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`. Crop lấy từ ảnh gốc; mắt `0,8d × 0,6d`, mặt mở rộng 10% mỗi phía.
- Windows chỉ nhận `Integrated Camera` và `Integrated IR Camera`; nguồn `0` đọc được. **Chưa xác minh camera USB rời.** Không có phiên đo trên ESP32 thật.
- ROCK 4D dùng RK3576/RK3576J theo [Radxa](https://docs.radxa.com/en/rock4/rock4d/hardware-use/hardware-info). Converter đã dùng `rk3576`, không dùng cấu hình RK3588 cũ. Toolkit2/Lite2 ghim 2.3.2; môi trường chuyển đổi Linux riêng vì [SDK chính thức giới hạn Torch ≤2.4.0](https://github.com/airockchip/rknn-toolkit2/blob/v2.3.2/rknn-toolkit2/packages/x86_64/requirements_cp312-2.3.2.txt).

## 2. Kết quả AI trên ảnh test hiện có

| Phép đo | Mẫu | Kết quả thực | Giới hạn |
|---|---:|---|---|
| Mắt, ảnh mắt gốc | 218 | Macro F1 **100%**; mỗi lớp 109 ảnh đúng | Chưa chứng minh tách người; không phải đánh giá crop YuNet trên video độc lập |
| Ngáp, toàn ảnh gốc | 215 | Macro F1 **99,53%**, F1 lớp yawn 99,53% | Toàn ảnh khác crop runtime; không dùng con số này thay kết quả crop mặt |
| Ngáp, crop YuNet đúng runtime | 215 | Macro F1 **90,46%**; F1 lớp yawn **88,54%**; recall yawn **80,19%** | Có 15 ảnh UNKNOWN, đã tính là bỏ sót; chưa có video/tách người độc lập |
| `.pt → ONNX`, mắt | 218 | Đồng nhất nhãn 100%; sai số xác suất tối đa `1,3923e-7`; giảm F1 0 điểm | Chưa đo RKNN |
| `.pt → ONNX`, ngáp toàn ảnh | 215 | Đồng nhất nhãn 100%; sai số xác suất tối đa `5,6674e-8`; giảm F1 0 điểm | Chưa đo RKNN hoặc INT8 |
| `ONNX → RKNN`, cả hai model | 2 artifact | Toolkit2 2.3.2 tạo thành công, target RK3576, chưa lượng tử hóa | Chưa suy luận blob/NPU trên bo; chưa đo F1 RKNN |
| Graph simulator Toolkit2 so với ONNX | 20 mắt + 20 ngáp, cân bằng lớp | Đồng nhất nhãn 40/40; sai số xác suất tối đa mắt `4,0330e-4`, ngáp `1,1930e-5` | Smoke trên graph dựng từ cùng ONNX/config; không suy luận blob `.rknn` xuất ra hoặc NPU thật |

Bằng chứng: [eye_onnx_parity.json](eye_onnx_parity.json), [yawn_onnx_parity.json](yawn_onnx_parity.json), [yawn_face_crop_test.json](yawn_face_crop_test.json).

[rknn_conversion.json](rknn_conversion.json) lưu host Linux x86_64, Python 3.12.10, Torch 2.4.0+cpu, ONNX 1.17.0 và Toolkit2 2.3.2. Ubuntu WSL có Python hệ thống 3.14; môi trường Python/SDK riêng nằm trong dự án, không thay Python hệ thống. `requirements-rknn-linux.lock.txt` là snapshot dependency chuyển đổi đã kiểm tra. Mỗi `.rknn` có kích thước 4.366.262 byte; SHA256 mắt `4242d1bd649c35a16e6197d069ade0c7f9c8be417b5d596ded6d10987661d3c3`, ngáp `95a006917c498fa5ee577ad0a1a8821c285781b87e545f2d07f8f33f4a309367`.

[rknn_simulator_smoke.json](rknn_simulator_smoke.json) kiểm tra RGB uint8 NHWC/normalization/xác suất/nhãn qua SDK simulator. Các trường `exported_rknn_blob_inference_tested`, `npu_inference_tested`, `physical_board_tested` đều false; chưa dùng kết quả smoke để kết luận F1 NPU đã đạt.

Confusion matrix crop ngáp, thứ tự `[no_yawn, yawn]`: `[[103,1],[11,85]]`, ngoài ra 15 mẫu bị từ chối do quality/detection. Evaluator không bỏ các mẫu này khỏi mẫu số. F1 classifier chọn lớp argmax; logic runtime còn yêu cầu confidence và thời gian liên tục, nên F1 ảnh không bằng recall của hệ thống.

Dataset cục bộ là snapshot phân loại: mắt train/val/test = **1112/122/218**, ngáp = **1111/122/215**. Bbox toàn ảnh phù hợp phân loại, không chứng minh model định vị mắt/mặt. Không phát hiện ảnh có cùng hash qua các split trong kiểm tra trước; điều đó chưa chứng minh khác người hoặc clip nguồn. Chưa tải/thêm dữ liệu video mới hoặc fine-tune trên dữ liệu cabin trong phiên này.

## 3. Camera và video

| Phiên | Dữ liệu thực | Kết quả |
|---|---|---|
| Camera PC ONNX, 640×480 | 591 frame/20 s | **29,55 FPS**, p95 đọc frame→quyết định **31 ms**, không lỗi runtime; NORMAL 400, UNKNOWN 191 |
| Ghi camera thật | 159 frame, thời gian lấy frame 11,593 s | AVI kèm sidecar timestamp thật; không giả định tốc độ quay là 30 FPS của header |
| Replay clip camera thật | Đọc hết 159 frame | UNKNOWN toàn bộ (`no_face`); mặt bị cắt/lệch trong clip, chưa có kết quả sự kiện để nghiệm thu |
| Fixture video kỹ thuật | 135 frame ở 15 FPS danh nghĩa, 8,933 s từ frame đầu đến cuối | 135 frame quality usable; cả hai classifier chạy; xác nhận 1 đợt ngáp; **0 frame bật còi** |

Bằng chứng camera: [summary](camera_live/20261006T061106_518319Z.summary.json), CSV/JSONL cạnh file. UNKNOWN gồm `blurry` 71, `uncertain_eyes` 30, `no_face` 90; khoảng 32,3% frame không đủ quan sát. Các số này cho biết trạng thái quan sát, chưa đánh giá đúng/sai vì chưa gán nhãn.

Bằng chứng video: [clip camera](camera_recording.avi) và [summary replay](video_replay/20261006T061647_295611Z.summary.json); [fixture](video_fixture.avi), [provenance fixture](video_fixture.fixture.json) và [kết quả lần kiểm tra cuối](video_fixture_final/20261006T071631_526750Z.summary.json).

Fixture lặp lại ảnh tĩnh đã chọn để kiểm tra decoder→YuNet→crop→classifier→logic thời gian. Nó **không mô phỏng chuyển động ngáp thật** và không được tính vào tập nghiệm thu ≥30 sự kiện. Throughput replay cũng không phải FPS camera/NPU trên bo. Lần replay cuối chạy đồng thời kiểm tra phần mềm khác; không dùng tốc độ này làm benchmark độc lập.

## 4. Phần mềm đã hoàn thiện và kiểm thử

`driver_monitor.core` nhận Observation theo tên lớp, giữ UNKNOWN đúng nghĩa và chỉ xác nhận khi frame mới, liên tục. Đã loại cửa sổ ngáp theo FPS, ngáp đơn bật còi và việc tính thời gian mất frame thành nhắm mắt liên tục. Ngáp và chớp mắt tăng riêng tạo WARNING; chỉ kết hợp cả hai mới bật còi, ngoại trừ nhắm mắt kéo dài. Hồi phục cần 1 s hợp lệ; UNKNOWN tắt ngay/ngắt chuỗi xác nhận.

Camera dùng hàng đợi frame mới nhất. Video dùng PTS hoặc sidecar, kiểm tra timestamp/tổng frame. Có xoay ảnh, ROI ghế lái, kiểm tra chất lượng, backend chung và chạy headless. GUI hiển thị trạng thái mắt, ngáp/xác suất, FPS, độ trễ và số sự kiện. Khởi động thiếu model/camera cũng sinh lỗi UNKNOWN trong nhật ký; thoát/lỗi đóng tài nguyên và gửi tắt.

Serial có ACK đúng lệnh, heartbeat 500 ms, kiểm tra dữ liệu mới ≤250 ms, reconnect và chờ ESP32 boot. Đã xử lý trường hợp lệnh bật cũ bị giữ trong lúc kết nối chậm. Firmware giới hạn dòng, ACK, startup tắt và watchdog 2 s. Nhật ký có config/model/source hash, xác suất, lý do, quality, FPS, p95, lỗi thiết bị và CPU/RAM/nhiệt độ nếu hệ điều hành cho đọc.

Phiên triển khai ban đầu ghi nhận 38 test Python đạt. Sau các bản sửa camera và dọn thư mục ngày 07/10/2026, lần chạy hiện tại có **69 test đạt**: 67 test runtime/logic/model/vision/serial/evidence và 2 test wrapper PC. Prototype tìm mặt bằng YOLO cũ đã được dọn vì luồng chính dùng YuNet. Bao phủ FPS thay đổi, timestamp đảo, frame cũ/khoảng mất frame, confidence thấp, ngáp đơn/hai đợt, nhắm mắt/hồi phục, driver đổi, ACK/timeout/reconnect, mất freshness khi kết nối chậm, lỗi startup và cleanup khi còi đang bật. Test adapter RKNN kiểm tra RGB uint8 NHWC/không chia 255 hai lần bằng transport giả; không phải suy luận NPU.

Host C++ biên dịch trực tiếp sketch với I/O giả đã đạt startup, ACK, watchdog đúng 2000 ms, heartbeat, lệnh sai, tràn dòng và rollover millis. Đây là mô phỏng host, **chưa cross-compile/nạp ESP32**. `pip check`, kiểm tra cú pháp Python và shell cài đặt đạt. [software_verification.json](software_verification.json) lưu bằng chứng kiểm tra tự động/hashes; kết quả trên phần cứng còn false.

## 5. Đối chiếu tiêu chí nghiệm thu

| Tiêu chí đã chốt | Hiện trạng |
|---|---|
| F1 mắt ≥90%, ngáp ≥85% trên test độc lập | Có F1 ảnh cũ; chưa đủ bằng chứng độc lập theo người/crop mắt thực |
| Recall nhắm kéo dài ≥90%, báo nhầm ≤1 lần/giờ | Chưa đo trên video có nhãn; chưa đủ 30 sự kiện và 2 giờ bình thường |
| Pipeline bo ≥15 FPS, p95 ≤200 ms | PC đạt về tốc độ phiên 20 s; Radxa chưa đo |
| Còi bật ≤300 ms sau xác nhận | Chưa đo GPIO/âm thanh/serial ESP32 thật |
| F1 RKNN giảm ≤2 điểm so với `.pt` | ONNX đạt trên ảnh cũ; RKNN và INT8 chưa chuyển/đo |
| Hoạt động 2 giờ, camera/model/serial lỗi rõ | Logic/logging và lỗi giả đã kiểm thử; thử dài/phần cứng chưa làm |

Không đánh dấu hệ thống đã nghiệm thu. Đặc biệt, che mắt/kính phản xạ cần video thật để xác minh gate quality/confidence; hai classifier hiện chỉ có hai lớp, chưa có model riêng phân loại mọi dạng che mắt. Bản đầu áp dụng cabin đủ sáng; GPS/SMS/giọng nói/danh tính/dashboard từ xa nằm ngoài phạm vi.

## 6. Bàn giao và việc còn phụ thuộc dữ liệu/bo

Trong phiên triển khai ban đầu, gói `dist/driver-monitor-rock4d.zip` chứa code dùng chung, model ONNX/YuNet, manifest, config, firmware/sơ đồ nối dây, script setup và mẫu systemd. Gói `dist/driver-monitor-rock4d-rknn.zip` thêm cả hai model nền RK3576 và giữ ONNX để đối chiếu trên bo. Các ZIP và kết quả kiểm tra ZIP này đã được dọn ngày 07/10/2026 vì không phản ánh bản PC hiệu chỉnh hiện tại. `tools/build_radxa_bundle.py` vẫn được giữ để tạo gói mới; mặc định chọn manifest nền. Không sao chép venv Windows/Linux hoặc video cá nhân vào gói bo.

1. Cắm/căn camera USB rời và kiểm tra source đúng; thu video cabin có nhãn, giữ ≥2 người test trong tổng ≥5 người.
2. Dùng validation hiệu chỉnh/cân nhắc fine-tune crop rồi khóa config/model. Dùng `evaluate-session`/`evaluate-study` báo cáo test theo người/ánh sáng; không dùng fixture kỹ thuật làm dữ liệu nghiệm thu.
3. Cài Linux ARM64 cho ROCK 4D; lưu RAM/OS/Python/driver/camera/serial. Kiểm tra ONNX CPU trước, chạy RKNN đã chuyển, xác minh parity trên bo và đo NPU.
4. Đo tốc độ/nhiệt độ/CPU/RAM, còi và chạy liên tục 2 giờ; thử rút camera/serial, dừng process, mất mặt và nhiều mặt. Chỉ bật systemd sau khi chạy tay ổn định.

Lệnh thực hiện cụ thể ở [README](../README_DRIVER_MONITOR.md), [triển khai Radxa](../DEPLOY_RADXA.md), [thu/gán nhãn](../data_collection/README.md) và [firmware/nối dây](../esp32_buzzer/README.md).
