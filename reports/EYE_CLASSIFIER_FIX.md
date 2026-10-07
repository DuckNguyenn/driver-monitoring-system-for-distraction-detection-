# Sửa lỗi nhắm một mắt bị báo hai mắt nhắm — 06/10/2026

Model mắt cũ có thể cho xác suất `Closed` rất cao trên mắt còn mở. Ảnh người dùng gửi có hai xác suất khoảng 1,00/0,99. Logic tổng hợp đã yêu cầu **cả hai mắt ≥0,8**; lỗi cần chữa nằm ở đầu ra classifier, không phải đổi điều kiện này thành phép OR hoặc sửa nhãn hiển thị đơn thuần.

## Tái hiện và nguyên nhân

Ca ảnh thật GENKI `file0127.jpg`, xem riêng vùng mắt và xác minh còn mở, cho P(nhắm) **0,92764/0,91446** qua YuNet và ONNX cũ. Ghép một vùng mắt mở này với một ảnh mắt nhắm thật tái hiện đúng trường hợp một mắt nhắm nhưng hai đầu ra đều Closed. Kiểm thử ban đầu `python -m unittest tests.test_eye_classifier -v` thất bại ở nhận diện mắt mở và xác nhận hai mắt.

PyTorch và ONNX cũ cho kết quả gần như giống hệt; thứ tự lớp vẫn `Closed, Open`. Thử chiều cao vùng mắt từ 0,6d xuống 0,5d/0,4d/0,3d chưa khắc phục ca này. Checkpoint huấn luyện trên ảnh mắt cắt sẵn chưa đủ đại diện vùng cắt YuNet có nền da/lông mày, mắt mở hẹp và góc nhìn khác. Các ảnh cắt sẵn đạt F1 cao không chứng minh nhận diện mắt trên camera đạt yêu cầu.

## Thay đổi đã dùng

`configs/camera_pc.yaml` chọn `models/eye_refined_v4/manifest.json`.

- Giữ YOLOv8n classification 224×224, 1.440.850 tham số, RGB/resize cạnh ngắn/center crop/255 và nhãn `Closed, Open`.
- Fine-tune **khối Classify**: convolution 1×1, tham số affine BatchNorm và linear, tổng 332.802 tham số. Kiểm kê thấy đúng năm tensor thay đổi; backbone và thống kê BatchNorm giữ nguyên.
- Dùng vùng cắt YuNet **0,8d × 0,6d** như runtime. Nhãn mỗi mắt được xem riêng; không suy ra từ nhãn ngáp/cười. Mẫu mờ/kính che hoặc không rõ trạng thái được giữ `Unknown`, không dùng làm nhãn training.
- Ca lỗi đã biết `file0127.jpg` được bổ sung vào train làm hard negative. Hai bản nhãn và lịch sử chuyển split được lưu; ca này **không phải kết quả test độc lập**.
- Bổ sung CEW từ nguồn tác giả để giữ phát hiện mắt nhắm thực tế: 200 mặt train, 50 validation, 60 audit/test, hai mắt mỗi mặt. Các mặt từ cùng ảnh gốc dùng cùng split. Checksum archive: `25c1eb8572a8755b87106a4bfea7f2dd89c1abaab95196eee51d43de9f8c6b48`.
- Sáu biến thể train áp dụng như nhau cho hai lớp: gốc, lật, xám, giảm sáng, xoay ±8°. Validation/audit không tăng cường ảnh. Loss cân bằng theo nguồn/lớp, chọn epoch bằng validation cùng điều kiện kiểm thử ca lỗi đã biết; epoch được chọn là **2**.
- Model ngáp đã sửa lỗi cười bị tính ngáp giữ checkpoint SHA `e6f2b598fd1ba96c3ecf5abef53da9fa968734064cae7264466ec50637c2a1be`.
- HUD phân biệt `Eyes:both open`, `Eyes:one closed`, `Eyes:both closed`, `unknown` và trạng thái đang ổn định. Không có R/L trên màn hình.

Manifest SHA: `2f2040049ffbe43c962c9f5542285b7983427d3836a47312d9fa49d3b1342847`.

Các bản chỉ sửa linear hoặc thiếu đủ dữ liệu Closed không đáp ứng đồng thời ca lỗi và độ nhạy mắt nhắm, nên không dùng làm cấu hình camera. Trọng số gốc và báo cáo thử nghiệm được giữ để đối chiếu.

## Kết quả đã kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Ca lỗi mắt mở hẹp | P(nhắm) 0,92764/0,91446 → **0,04614/0,04987**; đây là ca đã thêm vào train |
| Một vùng mắt nhắm + vùng mắt mở thật | Không xác nhận hai mắt nhắm, không bật còi |
| Chuỗi nháy một mắt từ các vùng cắt thật | Một eye cycle; 0 paired blink; không báo nhắm hai mắt |
| Chớp hai mắt ngắn từ vùng cắt thật | Một blink; không cảnh báo nhắm kéo dài |
| Nhắm hai mắt kéo dài từ vùng cắt thật | Vẫn bật cảnh báo khi đủ 1,5 s |
| 218 ảnh mắt cắt sẵn audit | Macro-F1 **100%**, bằng model cũ |
| 189 vùng mắt audit thực tế, 59 Open/130 Closed | Macro-F1 **97,54%**; Open bị xác nhận Closed ≥0,8: **1 → 0**; recall Closed ≥0,8: **93,85%**, bằng model cũ |
| 120 vùng mắt CEW Closed trong audit | Recall tại ngưỡng 0,8 **94,17%**, bằng model cũ; tập này chỉ có lớp Closed nên không dùng macro-F1 hai lớp để đánh giá |
| PyTorch → ONNX trên 407 vùng ảnh thật | Cùng nhãn **100%**; sai số xác suất tối đa **3,24×10⁻⁶** |
| Test tự động runtime/logic/serial/model | **64/64** đạt; tương thích PC cũ **2/2** đạt |

`tools/check_eye_classifier.py` tạo video lossless lặp lại ảnh thật và chạy qua toàn runtime:

- Video mắt mở: model cũ báo nhắm/cảnh báo trên 22/45 frame; model mới **0/45**, cả 45 frame có chất lượng usable. Cổng chất lượng không che lỗi để làm kiểm thử đạt.
- Video mặt có hai mắt nhắm thật: model mới vẫn cảnh báo trên **22/45 frame**, sau thời gian xác nhận.

Các video này là replay ảnh tĩnh để kiểm tra tích hợp. Các kiểm thử một mắt dùng hai vùng cắt thật để cô lập lỗi classifier/logic; chúng không phải video nháy tự nhiên của một người.

Camera `0`, 640×480, ONNX, profile PC chạy 10,05 s: **152 frame, 15,13 FPS, p95 32 ms**, 109 NORMAL/43 UNKNOWN, không lỗi runtime. Phiên có log `reports/eye_classifier_camera_check/20261006T162405_044346Z.*`. Không có nhãn hành động của người trước camera nên `accuracy` giữ null; không suy ra đã chữa chính xác ca nháy của người dùng từ lần chạy này.

Số liệu đầy đủ: `models/eye_refined_v4/validation.json`, `evaluation.json`, `reports/eye_refinement_pixels.json`, `reports/eye_classifier_replay.json`. Phiên thử mở camera trong sandbox thất bại cũng được lưu riêng, không gộp thành kết quả đo thành công.

## Chạy lại trên camera

Đóng cửa sổ đang chạy bằng Q/Esc, rồi mở lại để nạp trọng số mới:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display
```

Giữ đầu ổn định, thử mở cả hai mắt, nháy riêng từng mắt và nhắm cả hai mắt. `one closed` cần một mắt Closed và mắt kia Open đều ≥0,8; thiếu confidence hoặc đang đổi góc vẫn giữ unknown. Nháy một mắt chỉ tăng eye cycles sau mở lại; paired blink chỉ tăng khi chớp cả hai mắt ngắn. Cảnh báo kéo dài vẫn cần cả hai mắt Closed liên tục 1,5 s.

Đối chiếu mắt cũ cùng model ngáp đã sửa bằng cách thêm `--manifest models/smile_refined/manifest.json`.

## Phạm vi bằng chứng

Các tập ảnh phát triển chưa chứng minh tách theo người/clip; một số ảnh cabin là các frame gần nhau. Nhãn do coding agent xem bằng ảnh, cần người làm đề tài rà soát. Các tập audit đã được xem trong quá trình đánh giá ứng viên trước đó, nên không phải một vòng test cuối độc lập để nghiệm thu.

Chưa có video cabin gán nhãn ca nháy của người dùng, chưa đo báo nhầm/giờ hoặc recall sự kiện trên nhóm tài xế giữ riêng. Không tuyên bố đạt toàn bộ tiêu chí nghiệm thu. Trọng số mắt này chưa xuất RKNN/chạy NPU trên ROCK 4D.

Nguồn CEW: [trang dataset của tác giả](https://parnec.nuaa.edu.cn/_upload/tpl/02/db/731/template731/pages/xtan/ClosedEyeDatabases.html). Trích dẫn Song, Tan, Liu và Chen, *Eyes Closeness Detection from Still Images with Multi-scale Histograms of Principal Oriented Gradients*, Pattern Recognition 47 (2014), 2825–2838. Dữ liệu CEW phục vụ nghiên cứu; ảnh thô chỉ lưu trong cache, không đưa vào gói bàn giao.
