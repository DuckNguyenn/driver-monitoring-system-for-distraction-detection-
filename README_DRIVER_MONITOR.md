# HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ

> Tiếp tục theo feature: [bản đồ context](CONTEXT-MAP.md), [checkpoint mới nhất](CHECKPOINT.md), [docs](docs/README.md).

Bản dùng chung chạy YuNet để tìm mặt/tâm mắt và hai YOLOv8n **classification** để phân loại mắt/ngáp. Logic cảnh báo dùng thời gian, nhận dữ liệu thiếu là `UNKNOWN`, điều khiển ESP32 và lưu nhật ký. Đã chạy ONNX trên PC/qua video và chuyển hai model nền sang RKNN cho RK3576. Trọng số PC hiệu chỉnh hiện tại chưa chuyển RKNN; suy luận NPU và nghiệm thu trên bo còn chờ Radxa được cài đặt.

Kết quả thực đo mới nhất và giới hạn nằm trong [báo cáo fine-tune ảnh mờ](reports/BLUR_REFINEMENT.md). [Hướng dẫn Radxa](DEPLOY_RADXA.md) và [thu video/gán nhãn](data_collection/README.md) là các bước tiếp theo.

Báo cáo đồ án hiện tại: [Word](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.docx) và [PDF](reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.pdf). Phần thiết kế mô tả camera → PC/Radxa → ESP32 → buzzer cùng dashboard và app iPhone trong LAN, kèm lý thuyết và 18 hình. Các mục chưa có phép đo vẫn để trống. Xem [cấu trúc thư mục](REPOSITORY_STRUCTURE.md) để phân biệt runtime, dữ liệu huấn luyện, model và hồ sơ kiểm thử.

## Web và app iPhone trong cùng Wi-Fi

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor serve --source 0 --backend onnx --display
```

Cài API bằng `requirements-dashboard.lock.txt`; mở `http://127.0.0.1:8765` và nhập mã từ terminal. `serve` dùng profile PC hiện tại, mục tiêu preview 15 FPS; thêm `--display` để mở cửa sổ Driver monitor và truyền cùng khung hình đã vẽ lên web/app. Biểu đồ tách ba hàng Mắt 1, Mắt 2 và Ngáp. iPhone dùng IPv4 của PC và Expo Go với `npm.cmd run start:mobile`. Hướng dẫn cài, kết nối, API, systemd và giới hạn kiểm thử: [DASHBOARD.md](DASHBOARD.md).

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

Model ngáp PC đã được hiệu chỉnh ngày 07/10/2026: trên video camera người dùng gửi, bản trước xác nhận 0/2 lần, bản mới xác nhận 2/2 và không tính cười thành ngáp. Giữ ngưỡng 0,70/1 giây, EMA 0,20 giây và kiểm tra chất lượng ảnh. Video một người được dùng cho hiệu chỉnh; lần ngáp thứ hai giữ lại sau chọn model, nhưng chưa phải kiểm thử độc lập theo người. Dùng `--config configs/camera_yawn_previous.yaml` để đối chiếu hoặc quay lại bản trước. [Kết quả replay mới nhất](reports/BLUR_REFINEMENT.md).

Model mắt đã được hiệu chỉnh bằng dữ liệu bổ sung và kiểm tra nháy riêng một mắt, nhắm hai mắt thật, tương đương PyTorch/ONNX. Ca lỗi đã biết được thêm vào train; kết quả ảnh tĩnh chưa chứng minh độ chính xác trên camera của bạn. Thêm `--manifest models/smile_refined/manifest.json` để đối chiếu model mắt cũ và giữ model ngáp đã sửa. Trọng số mắt mới chưa có bản RKNN.

Model ngáp được bổ sung ảnh cười, chọn bằng validation và kiểm tra ảnh giữ riêng. Đây là model thử trên PC; chưa nghiệm thu video theo người hoặc NPU. Thêm `--manifest models/manifest.json` vào lệnh trên để đối chiếu model ban đầu với cùng ngưỡng camera. Cấu hình chung và RKNN gốc vẫn dùng model ban đầu.

Khung mắt hiển thị không có chữ R/L. `Eyes:both open` là hai mắt cùng mở, `Eyes:one closed` là một mắt nhắm và mắt kia mở với confidence đạt ngưỡng, `Eyes:both closed` là hai mắt cùng nhắm; kết quả chưa rõ giữ `unknown`. `Eyes P(closed)` hiển thị hai xác suất nhắm mắt; dấu `?` nghĩa là classifier chưa chạy trên vùng mắt đó. `Eye cycles total` cộng số lần đóng–mở của từng mắt, gồm cả nháy riêng một mắt hoặc đóng kéo dài. `Blink both` chỉ đếm chớp cả hai mắt có đoạn nhắm trùng nhau, kéo dài 0,05–0,5 s; `5s` là số chớp trong cửa sổ 5 giây, tổng đếm giữ theo tài xế hiện tại. Nháy riêng một mắt chỉ tăng `Eye cycles total`. Nhật ký vẫn giữ dữ liệu từng mắt để phân tích.

`Yawn P raw` là đầu ra classifier, `filtered` là xác suất dùng để quyết định. Profile PC thử bộ lọc EMA theo thời gian 0,20 s; cấu hình chung mặc định không lọc. `Yawn:confirm x/1s` là đang chờ xác nhận, `Yawn:yawn` là đã xác nhận một đợt. P gốc có thể biến động lúc bắt đầu/kết thúc ngáp. `UNKNOWN: uncertain_eyes` nghĩa là hai mắt chưa cùng đạt xác suất mở hoặc nhắm ≥0,8; mouth classifier hợp lệ vẫn được theo dõi, trong khi trạng thái tổng thể vẫn UNKNOWN và còi tắt.

Profile PC yêu cầu mắt mở chắc chắn liên tục 0,10 s để bắt đầu/kết thúc eye cycle. Nếu hình học mặt/mắt dịch chuyển khi đổi góc hoặc ngẩng đầu, runtime hiện `UNKNOWN: head_motion` và `Eyes:stabilizing ...s`, ngắt chuỗi eye cycle/blink/nhắm kéo dài, rồi chờ ổn định ít nhất 0,35 s. Model ngáp vẫn chạy nếu chất lượng mặt đạt. Các ngưỡng chuyển động là cấu hình thử; ca ảnh xoay không tăng chu kỳ sau sửa, nhưng chưa nghiệm thu recall trên video ngẩng đầu/chớp mắt tự nhiên.

Nhấn `Q` để thoát phiên cũ rồi chạy lại lệnh trên sau khi cập nhật code.

Ngưỡng mắt 6 là cấu hình thử PC, cần hiệu chỉnh bằng video có nhãn trước khi dùng cho nghiệm thu cabin/Radxa. Profile ảnh mờ dùng ngưỡng 16/5 đã chọn trên validation; xem [kết quả và cách chạy](reports/BLUR_REFINEMENT.md). Nếu điểm độ nét mặt hoặc mắt vẫn dưới ngưỡng, kiểm tra lấy nét và chiếu sáng phía trước mặt. Thông số `fps: 0.0` của `probe_camera.py` là giá trị camera trả về; FPS xử lý thực nằm trong HUD và file summary.

Kiểm tra chỉ số camera:

```powershell
& '.\.venv\Scripts\python.exe' tools/probe_camera.py
```

Chỉ số camera có thể đổi khi cắm/rút USB. Bản quay màn hình và nhật ký ngày 09/10/2026 đã có hình camera USB ở nguồn `0`, nhưng classifier còn bỏ sót ngáp. Chạy lại công cụ và dùng chỉ số trả về frame. Đóng ứng dụng khác đang giữ camera. Đặt camera ngang, thấy trọn khuôn mặt và cả hai mắt. Nếu khung hình bị xoay, thêm `--rotate 90`, `180` hoặc `270`; đây là phép xoay toàn frame, không khôi phục khuôn mặt bị cắt khỏi ảnh.

Chạy 20 giây, không mở cửa sổ:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --headless --duration 20 --log-dir reports/camera_live
```

## Test riêng hai model YOLOv8n đã train ban đầu

Chạy lần lượt, đóng phiên run/serve đang giữ camera trước khi thử. Công cụ luôn chọn `models/manifest.json` để tải checkpoint gốc `camera_classical/best_eye.pt` hoặc `camera_classical/best_yawn.pt`, dùng YuNet và ROI của profile PC. Nó hiển thị xác suất thô, báo chất lượng ảnh riêng, kể cả crop mờ; không dùng Monitor, EMA hoặc điều khiển ESP32.

```powershell
& '.\.venv\Scripts\python.exe' tools/test_original_model.py --name eye --source 0 --inspect-model
```

```powershell
& '.\.venv\Scripts\python.exe' tools/test_original_model.py --name yawn --source 0 --inspect-model
```

Nhấn `Q`/`Esc` để kết thúc. Cửa sổ phụ hiển thị đúng ảnh 224×224 model nhận. File CSV trong `reports/original_model_check/` lưu xác suất theo tên lớp; dữ liệu thiếu để trống. Thêm `--backend onnx` để kiểm tra bản ONNX xuất từ checkpoint gốc.

Ghi video gốc trong khi test model ngáp, để đối chiếu trường hợp gần–xa:

```powershell
& '.\.venv\Scripts\python.exe' tools/test_original_model.py --name yawn --source 0 --inspect-model --record
```

Giữ camera, góc đầu và ánh sáng ổn định. Thử lần lượt gần, khoảng cách ngồi lái thông thường và xa hơn; ở mỗi vị trí giữ miệng thư giãn 5 giây, thực hiện một lần ngáp rồi thử cười. Dòng `Face ROI` hiển thị kích thước crop theo pixel và tỷ lệ chiều rộng frame, không quy đổi thành khoảng cách vật lý. `usable` chỉ cho biết crop qua kiểm tra chất lượng ảnh; model vẫn có thể phân loại sai.

`--record` lưu AVI **FFV1 lossless** chưa vẽ chữ/khung, `.timestamps.json` chứa thời điểm và hash frame gốc, `.metadata.json` ghi model/preprocessing/cấu hình, cùng CSV ghi bbox, kích thước ROI, xác suất và hash ảnh RGB đầu vào. Giữ các file cùng tên cạnh nhau để phát lại đúng thời gian; AVI dùng FPS danh nghĩa 30, còn runtime đọc thời gian thực từ sidecar. Chỉ ghi các frame được công cụ xử lý, không lưu hàng đợi frame cũ. Video này chưa có nhãn chuẩn; file metadata giữ `ground_truth_reviewed: false`.

Đối chiếu `yawn_error.mp4` với CSV gốc xác nhận model ngáp ban đầu nhận nhầm miệng khép ở thời gian trên cửa sổ 28,58 s (`P=0,979`) và 43,27 s (`P=0,763`). Đoạn sau mặt lớn hơn trên màn hình, nên chưa thể quy lỗi chỉ cho khoảng cách xa. Đây là video quay màn hình, không giữ nguyên pixel camera; các thử nghiệm trên crop trích chỉ phục vụ chẩn đoán, không dùng train/chọn checkpoint hoặc nghiệm thu. Trọng số và ngưỡng chưa thay đổi. [Bằng chứng đối chiếu](reports/usb_yawn_diagnosis/original_distance_check.json).

**Hai video camera gốc ngày 10/10 xác nhận độ nhạy với độ phân giải:** bản ghi `20261010T132214_553016Z_yawn.avi` có 502 frame/33,437 s, bản ghi `20261010T133911_739010Z_yawn.avi` có 167 frame/11,078 s. Toàn bộ 669 hash frame và 616 hash đầu vào khớp CSV khi phát lại. Model gốc nhận miệng khép ở cự ly trung bình, giây 8,016 của clip thứ hai, thành ngáp (`P=0,999927`); API Ultralytics cũng trả cùng kết quả. Bản USB robust giảm lỗi này (`P=0,001133`) nhưng bỏ sót đoạn ngáp mô phỏng trung bình đã xem ở 8,55–9,35 s: cả 11 frame hợp lệ đều có điểm dưới 0,70, tối đa 0,369. Ở gần, frame ngáp giây 2 có điểm USB robust 0,9953 nhưng chất lượng `blurry`, nên runtime vẫn giữ `UNKNOWN`.

Trong clip gần–xa, chỉ giảm độ phân giải của cùng một crop ngáp giây 10 rồi khôi phục kích thước làm điểm USB robust từ 0,854 xuống 0,082 (tỷ lệ 0,5); crop/vùng mặt và trọng số giữ nguyên. 49/51 frame `no_face` tìm được crop khi tạm bỏ điều kiện mặt tối thiểu 80 pixel; 2 frame còn lại vẫn không có mặt hợp lệ. Phép thử này chỉ khoanh vùng nguyên nhân, **chưa đổi ngưỡng kích thước/chất lượng hoặc model đang dùng**. Hai clip được giữ để chẩn đoán, không train/chọn checkpoint và chưa phải kiểm thử độc lập theo người. [Biểu đồ so sánh](reports/usb_yawn_diagnosis/original_raw_distance_check.png) · [Số liệu](reports/usb_yawn_diagnosis/original_raw_distance_check.json).

Phát lại video camera đã ghi:

```powershell
& '.\.venv\Scripts\python.exe' tools/test_original_model.py --name yawn --source 'reports/usb_camera_check/20261010T110453_140956Z.avi' --inspect-model --realtime
```

Đây là công cụ kiểm tra dự đoán trên camera/video; CSV chưa gán nhãn không cung cấp F1 hoặc tỷ lệ phát hiện sự kiện ngáp.

## Model ngáp trên camera USB

**Profile thử mới nhất: `configs/camera_usb_robust.yaml`.** Bản này bổ sung dữ liệu góc thấp, nhiễu cảm biến, biến động crop, Gaussian blur và JPEG trong huấn luyện; giữ backbone/conv/BN, model mắt, một lượt suy luận ngáp và các ngưỡng cũ. Phát lại ba clip phát triển nhận 6/6 đợt, không đếm trùng hoặc nhận ngáp thừa trong các khoảng bình thường/cười đã gán nhãn. Mẫu ngáp hở răng ở giây 12 của clip phát triển tăng từ 0,169 lên 0,973; ba biến thể nhiễu nhẹ đạt 0,948–0,975. Kết quả phát triển này chưa đại diện cho mọi video camera mới.

**Kiểm tra lossless ngày 10/10/2026 chưa đạt:** clip mới `20261010T110453_140956Z.avi` dùng đúng profile robust, ghi đủ 424 frame/37,969 giây bằng FFV1. Hash BGR từng frame, RGB 224×224 từng đầu vào, bbox và xác suất phát lại đều trùng lúc quay. Hai đợt ngáp đã xem ở 5,75–12,75 s và 28,25–34,90 s: chỉ xác nhận đợt thứ hai ở 29,891 s; không đếm ngáp trong 22,419 giây bình thường/cười đã đánh dấu. Đợt đầu chỉ giữ điểm sau EMA ≥0,70 liên tục tối đa 0,890 s, chưa đủ 1 giây. Bỏ EMA, padding vuông hoặc giữ bbox cố định đều chưa khôi phục đợt đầu. Clip được khóa để kiểm tra, không train/chọn checkpoint hoặc hạ ngưỡng theo clip này. Đây là kiểm tra cùng người phát triển, chưa nghiệm thu độc lập. [Biểu đồ kiểm tra](reports/usb_yawn_diagnosis/usb_lossless_check.png).

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor serve --config configs/camera_usb_robust.yaml --source 0 --backend onnx --display
```

**Lưu ý về bằng chứng video:** clip `20261009T120936_563235Z.avi` được bộ ghi cũ nén MJPG. Điểm lưu lúc quay chỉ xác nhận 1/2 đợt, còn phát lại AVI với cùng model cũ lại nhận 2/2. Tại giây 8, giữ bbox gốc nhưng đổi sang pixel giải mã làm điểm từ 0,699 thành 0,978. Vì vậy kết quả phát lại không chứng minh nhận diện trực tiếp đã đạt. Bộ ghi hiện dùng **FFV1 lossless**, thêm SHA256 frame gốc và ảnh đầu vào từng lượt; bản ghi ngày 10/10 đã xác minh giữ nguyên toàn bộ pixel/đầu vào/điểm, đồng thời tái hiện một đợt ngáp còn bị bỏ sót. [Biểu đồ đối chiếu MJPG cũ](reports/usb_yawn_diagnosis/usb_low_angle.png).

```powershell
& '.\.venv\Scripts\python.exe' tools/record_yawn_check.py --source 0 --config configs/camera_usb_robust.yaml --inspect-model --output-dir reports/usb_camera_check
```

Dừng `serve` bằng `Ctrl+C` trước khi ghi. Giữ nguyên góc đang gây lỗi, làm theo hướng dẫn 38 giây và giữ các sidecar cạnh AVI. FFV1 tốn dung lượng hơn MJPG; không tự chuyển sang nén mất pixel khi codec chưa có. Các bản dưới đây được giữ làm đối chiếu.

Nhật ký phiên `20261009T100830_127478Z`, đoạn 24–32 giây, có 89/89 frame đạt chất lượng nhưng điểm ngáp sau lọc chỉ tối đa **0,527**; không frame nào đạt ngưỡng 0,70. Phát lại xác suất khi bỏ EMA vẫn không xác nhận được đợt ngáp. Bản quay màn hình cho thấy crop mặt dọc qua center crop 224×224 có thể mất phần dưới miệng. Đây là dấu hiệu cần kiểm chứng bằng video camera sạch; chữ/khung vẽ và nén trong bản quay màn hình làm ảnh trích khác đầu vào gốc.

Video USB sạch `20261009T105555_466558Z.avi` đã tái hiện lỗi. Profile **thử riêng** `configs/camera_usb_refined.yaml` dùng model ngáp được fine-tune cục bộ từ `yawn_camera_refined`: chỉ cập nhật Linear 1280→2, giữ backbone, conv, BN, model mắt và preprocessing. Trộn dữ liệu train cũ với crop đúng runtime từ đoạn ngáp đầu, miệng bình thường và cười trong clip USB. Đoạn ngáp thứ hai không dùng để train/chọn checkpoint. Giữ ngưỡng 0,70/1 giây, EMA 0,20 giây, ngưỡng nét 20/6; vẫn chỉ chạy một lượt classifier ngáp. Profile PC mặc định chưa đổi.

| Profile | Đợt ngáp nhận được trong clip USB 38 giây |
|---|---:|
| `camera_pc.yaml` | 0/2 |
| `camera_usb_dual_view.yaml` | 1/2 |
| `camera_usb_refined.yaml` | 2/2 |

Bản fine-tune xác nhận ở 8,078 s và 29,344 s; không có đợt ngáp thừa trong các khoảng đã gán nhãn bình thường/cười. Đây là hồi quy phát triển trên một người/clip, chưa đo nghiệm thu độc lập hoặc báo nhầm theo giờ.

**Lần thử trực tiếp mới vẫn bỏ sót ngáp:** phiên `20261009T120313_030301Z` đã nạp đúng ONNX của `yawn_usb_refined`. Đoạn 16–18 giây tương ứng phản ánh của người dùng có 22/22 frame đạt chất lượng, nhưng xác suất thô chỉ 0,0004–0,1815; phát lại khi bỏ EMA vẫn không xác nhận ngáp. Kết quả 2/2 trong bảng chỉ áp dụng cho video cũ. Bản USB chưa đạt ở góc camera thấp mới; cần ghi video gốc mới để kiểm tra vùng cắt và tổng quát hóa, chưa thay đổi ngưỡng hoặc trọng số theo ảnh chụp màn hình.

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor serve --config configs/camera_usb_refined.yaml --source 0 --backend onnx --display
```

Lệnh trên mở cửa sổ Driver monitor và phục vụ cùng ảnh trên web/app. Đóng phiên `run`/`serve` cũ trước khi chạy; một camera chỉ do một tiến trình giữ. Có thể thay `serve` bằng `run` để thử chỉ trên PC. Quay lại bản đối chiếu bằng `--config configs/camera_pc.yaml`.

Để ghi video sạch kèm đúng ảnh đầu vào và điểm từng lượt, dừng `serve` bằng `Ctrl+C`, rồi chạy:

```powershell
& '.\.venv\Scripts\python.exe' tools/record_yawn_check.py --source 0 --config configs/camera_usb_refined.yaml --inspect-model --output-dir reports/usb_camera_check
```

Công cụ đếm ngược 5 giây rồi hướng dẫn 38 giây: bình thường → ngáp → bình thường → cười nhe răng → bình thường → ngáp → bình thường. AVI FFV1 lưu nguyên pixel frame trước khi vẽ chữ/khung; cửa sổ phụ hiển thị ảnh 224×224 đúng đầu vào model. Giữ cạnh AVI các file `.timestamps.json`, `.probe.jsonl`, `.protocol.json`; CSV mẫu chưa có nhãn, cần xem lại video và gán đúng khoảng thời gian. Công cụ này ghi dữ liệu chẩn đoán, không điều khiển còi; suy luận trong lúc ghi có thể làm giảm tốc độ lấy mẫu, thời gian thật nằm trong sidecar.

Profile đối chiếu `camera_usb_dual_view.yaml` dùng trọng số cũ với center crop và một lượt thêm viền để giữ toàn ROI mặt; lấy điểm ngáp lớn hơn, chưa hiệu chuẩn. Nó giữ 2/2 đợt webcam cũ và cải thiện ảnh trích từ bản quay màn hình, nhưng chỉ đạt 1/2 trên video USB sạch nên chưa đạt hồi quy USB. Không dùng bản quay màn hình để train hoặc tính độ chính xác nghiệm thu. [Bằng chứng, recipe fine-tune và giới hạn](reports/usb_yawn_diagnosis/diagnosis.json).

## Fine-tune ngáp theo khoảng cách camera

Quy trình thu crop camera gần–trung bình–xa, gán nhãn bằng timestamp thật, downsampling native ROI và blur nhẹ trước preprocessing 224×224 đã có ở [hướng dẫn fine-tune theo khoảng cách](data_collection/yawn_distance/README.md). Cấu hình đầy đủ: `configs/yawn_distance_training.yaml`; yêu cầu cả train/val cho ba cự ly.

Phiên gần/trung bình dùng riêng `configs/yawn_near_medium_training.yaml`, hai clip camera train và validation ảnh cũ (`static_only`). Không đổi split của clip train và không dùng clip lỗi đã khóa để chọn checkpoint. Ứng viên được lưu ở `models/yawn_near_medium_candidate/`; chất lượng trên camera validation mới và người độc lập vẫn cần kiểm chứng. Profile chạy thử sau khi xuất và kiểm tra parity:

Bản CPU thử đã nhận 4/4 đợt trên hai clip train, nhưng bỏ sót clip USB góc thấp giữ riêng nên chưa thay profile chính. Để train bằng GPU Kaggle, dùng [dataset ZIP và notebook đã đóng gói](kaggle_upload/README.md), có lựa chọn checkpoint Kaggle ban đầu hoặc bản USB refined. Notebook không tiếp tục từ ứng viên CPU này.

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --config models/yawn_near_medium_candidate/runtime.yaml --source 0 --backend onnx --display
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

### Test riêng model mắt đang dùng trong runtime

Công cụ `tools/test_original_model.py` mặc định vẫn nạp checkpoint ban đầu. Thêm `--use-config-model` để kiểm tra đúng model được manifest của profile đang chạy tham chiếu. Với ứng viên ngáp Kaggle gần/trung bình, model mắt vẫn là `eye_refined_v4`; lần fine-tune Kaggle đó không cập nhật model mắt.

Dừng phiên `run`/`serve` đang mở camera trước khi ghi một phiên kiểm tra riêng:

```powershell
& '.\.venv\Scripts\python.exe' tools/test_original_model.py --name eye --use-config-model --config models/yawn_kaggle_near_medium/runtime.yaml --backend onnx --source 0 --inspect-model --record --duration 60 --output-dir data_collection/eye_medium/videos
```

Ở khoảng cách trung bình: giữ đầu yên, mở hai mắt trong 15 giây đầu; tiếp theo chớp bình thường, nhắm hai mắt khoảng 2 giây rồi mở, nháy riêng từng mắt, cuối cùng đổi góc đầu khi mắt vẫn mở. Q/Esc kết thúc sớm. Công cụ hiển thị **xác suất thô** và chất lượng riêng, không chạy logic cảnh báo hay ESP32.

Ảnh camera gốc được ghi FFV1 với timestamp/hash để phát lại đúng pixel; CSV chứa xác suất, tọa độ/kích thước và độ nét/độ sáng từng crop. Cửa sổ phụ hiển thị đúng ảnh 224×224 mà classifier nhận. Metadata lưu checksum model/manifest và thứ tự crop: mắt trái rồi mắt phải theo tài xế; trên màn hình vẫn dùng `Eye 1`/`Eye 2`, không thêm R/L. Hành động thực tế cần được xem và gán nhãn sau khi ghi; không tự coi hướng dẫn thu hình là ground truth.

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
