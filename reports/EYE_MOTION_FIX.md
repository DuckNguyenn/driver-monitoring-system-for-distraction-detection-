# Eye cycle tăng khi đổi góc/ngẩng đầu — 06/10/2026

Người dùng xác nhận bộ đếm chỉ tăng khi đổi góc/ngẩng đầu, không tăng khi giữ đầu yên. Bản sửa dùng hình học YuNet để ngắt các chuỗi của kênh mắt khi quan sát đang chuyển động, đồng thời xác nhận trạng thái mở trước khi chốt sự kiện. Không huấn luyện lại hoặc thay weights của model mắt trong bản sửa này.

## Tái hiện lỗi trước sửa

Phiên `logs/20261006T144941_940907Z` có 1.835 frame trong 122,75 giây; cuối phiên đếm 55 chu kỳ mắt trái, 20 chu kỳ mắt phải và 8 blink hai mắt. Có 941 frame `uncertain_eyes`. Phiên không có gán nhãn/video kèm theo, nên không tự coi cả 75 chu kỳ là nhầm. Một đoạn cho thấy một mắt đổi từ P(nhắm) 0,12 → 0,997 → 0,144 qua các frame 313–315, chỉ khoảng 125 ms, và tăng thêm một chu kỳ.

Ca tái hiện có pixel thật dùng `tests/fixtures/eye_motion/open_face.jpg` từ [MPLab GENKI-4K](https://mplab.ucsd.edu/398/), file0105.jpg. Hai mắt mở đã được kiểm tra trực quan. Xoay ảnh 15° rồi trả lại không thay đổi trạng thái mí mắt, nhưng YuNet + classifier ONNX thật cho xác suất một mắt **0,076 → 0,814 → 0,076**; Monitor cũ tăng một eye cycle. Crop mặt vẫn đạt điều kiện chất lượng. Nguồn/checksum/nhãn kiểm tra thủ công nằm trong `source.json` cùng thư mục.

Ca unit này đã chạy đỏ trước sửa: `test_real_open_face_roll_and_return_does_not_create_an_eye_cycle`, kết quả `1 != 0`. Vòng kiểm tra full runtime hiện nằm ở `tools/check_eye_motion.py`; chạy cả chính sách cũ và mới trên cùng một video FFV1 từ ảnh này. Chính sách cũ được đối chiếu bằng ngưỡng chuyển động rất lớn và xác nhận mở 0 s, dùng cùng model/pixel.

## Chẩn đoán

Đã kiểm tra ba khả năng: vùng cắt mắt thay đổi theo pose; thiếu tín hiệu ngắt chuỗi khi chuyển động; thời gian xác nhận mở quá ngắn. Chỉ xoay các ảnh mắt Open đã cắt từ tập train ±10/15/20° không tạo lỗi Closed ≥0,8, nhưng xoay toàn ảnh mặt và cắt lại bằng YuNet tạo được lỗi. Thử căn ngang vùng mắt trên ca mặt này vẫn cho P(nhắm) khoảng 0,85, nên không đưa phép căn ngang đó vào runtime. Các phép xoay thử dùng API [OpenCV geometric transforms](https://docs.opencv.org/4.11.0/da/d54/group__imgproc__transform.html).

Kết luận trong phạm vi đã kiểm tra: classifier có thể nhạy với ROI/landmarks khi đầu đổi góc; bộ đếm trước đây dùng chuỗi xác suất và chưa có thông tin hình học để loại lần chuyển trạng thái đó. Không có bằng chứng đã sửa chất lượng phân loại của model ở mọi góc camera.

## Thay đổi

- `Vision.observe(frame, timestamp=...)` đo vị trí tâm mắt/mũi, khoảng cách hai mắt, góc đường nối hai mắt và vị trí mũi tương đối với hai mắt. Đây là tín hiệu chuyển động **2D**, không phải góc pitch/yaw 3D được hiệu chuẩn. Không dùng biến dạng miệng để quyết định chuyển động mắt.
- So sánh với một cửa sổ **0,30 s**: dịch chuyển hoặc thay đổi tỷ lệ/hình học ≥**0,08** theo khoảng cách hai mắt, hoặc đổi góc đường mắt ≥**3°**, đánh dấu `eye_quality=head_motion`. Cả chuyển động đột ngột và thay đổi tích lũy trong cửa sổ đều được kiểm tra. Các ngưỡng là cấu hình thử, chưa khóa bằng validation có nhãn.
- Chờ ổn định ít nhất **0,35 s** sau tín hiệu chuyển động gần nhất. Khi phát hiện pose mới, bỏ mốc pose cũ để một tư thế mới giữ yên có thể trở lại hợp lệ. Khoảng mất frame, mất mặt hoặc thay tài xế không nối lịch sử hình học cũ.
- Tách `Observation.eye_quality` khỏi chất lượng toàn frame. `head_motion` ngắt eye cycle/blink và xác nhận nhắm kéo dài, đưa trạng thái tổng thể thành UNKNOWN/còi tắt; phân phối ngáp hợp lệ vẫn được theo dõi. Các chu kỳ đã xác nhận trước đó không bị xóa khi chỉ chuyển động đầu.
- Profile PC yêu cầu **Open ≥0,8 liên tục 0,10 s** trước khi bắt đầu/kết thúc một eye cycle. Một frame “mở” thoáng qua không chia một đoạn nhắm thành nhiều chu kỳ. Thời lượng nhắm vẫn đo đến frame mở đầu tiên, không cộng thêm thời gian chờ xác nhận vào khoảng 0,05–0,5 s của blink.
- `UNKNOWN: head_motion` và `Eyes:stabilizing ...s` hiển thị lý do chờ; R/L vẫn được bỏ khỏi màn hình. CSV/JSONL lưu eye quality, góc đường mắt, các mức thay đổi và thời gian chờ còn lại. Raw xác suất mắt được giữ để phân tích.

Model mắt/ngáp và preprocessing của classifier không đổi. Ngưỡng nhắm hai mắt ≥0,8 trong 1,5 s vẫn dùng cho các quan sát hợp lệ; chuyển động ngắt xác nhận này. `MonitorConfig.eye_event_open_seconds` mặc định 0 để giữ tương thích với caller cũ; profile PC đặt 0,10. Runtime camera/video đều truyền timestamp của nguồn vào Vision.

## Kiểm thử thực hiện

| Hạng mục | Kết quả |
|---|---|
| 59 test driver_monitor + 2 test tương thích PC | Đạt |
| Full runtime trên 45 frame ảnh mở mắt đổi góc | Cách đếm cũ: 1 eye cycle; bản sửa: 0; không có blink hai mắt |
| Frame eye quality=head_motion trong replay | 12/45 |
| Giữ pose mới yên sau chuyển động | Hết thời gian chờ và trở lại usable trong ca kiểm thử |
| Dịch chuyển mũi mô phỏng pitch, tịnh tiến, thay tỷ lệ, chuyển động chậm | Ngắt chuỗi đúng ở các ca đã kiểm tra |
| Nhiễu landmarks nhỏ và pose giữ yên | Không báo chuyển động trong ca kiểm thử |
| Chớp mắt bằng tín hiệu Open/Closed có nhãn, FPS 5/15/30/60 | Đếm một blink, không cộng thời gian xác nhận mở vào thời lượng nhắm |
| Nhắm kéo dài bằng tín hiệu hợp lệ, ngáp khi kênh mắt chuyển động | Logic cảnh báo và theo dõi ngáp đạt |

Ca full runtime dùng video ghép từ một ảnh mở mắt, không phải video hành vi tự nhiên. Test blink/nhắm kéo dài ở bảng trên kiểm tra chính sách bằng xác suất có nhãn, chưa chứng minh model nhận đúng blink ngoài thực tế.

Camera 0 đã chạy **281 frame/10 s (28,1 FPS), p95 32 ms**, không lỗi thiết bị. 246 frame `head_motion`, 15 `blurry`, 8 `uncertain_eyes`, 12 NORMAL; chỉ 20 frame có eye quality usable. Bộ đếm không tăng trong lần đo này, nhưng không có gán nhãn hành vi/pose nên **không dùng kết quả đó làm bằng chứng độ chính xác hay recall blink**. Tỷ lệ mắt chưa dùng được cao là giới hạn cần kiểm tra bằng video giữ đầu yên và video chuyển động có nhãn; không thể kết luận các frame đều là chuyển động thật thay vì jitter detector.

Bằng chứng: `reports/eye_motion_replay.json`, `reports/eye_motion_replay/*/*.csv`, `reports/eye_motion_camera_check/20261006T151319_704998Z.*`, ảnh minh họa `report_assets/face_motion_failure.png` và `report_assets/eye_motion_hud.png`.

## Chạy lại

Thoát phiên cũ bằng Q/Esc để nạp code/config mới, rồi chạy:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display
```

Tái lập kiểm tra lỗi qua toàn bộ pipeline:

```powershell
& '.\.venv\Scripts\python.exe' tools/check_eye_motion.py
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -p test_head_motion.py -v
```

Kiểm tra bằng video thực cần phân biệt: giữ đầu yên/mắt mở; đổi góc/ngẩng đầu/mắt mở; chớp hai mắt; nháy riêng một mắt; nhắm kéo dài. Đếm có thể bỏ sót trong thời gian head_motion; detector chuyển động không thay thế fine-tuning model mắt với crop/góc camera thực. Chưa nghiệm thu góc đặt camera của người dùng, recall sự kiện, báo nhầm/giờ hoặc Radxa NPU.
