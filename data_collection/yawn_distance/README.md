# Fine-tune ngáp theo khoảng cách camera

Pipeline này bắt đầu từ `models/yawn_usb_robust/best_yawn.pt`, là bản đã fine-tune từ model Kaggle ban đầu. Chỉ huấn luyện thêm model ngáp. Backbone được giữ cố định; phần Classify gồm conv, tham số affine BN và Linear được cập nhật với learning rate `0,0001`. Thống kê chạy của BN giữ nguyên. Model mắt, YuNet, logic còi và cấu hình triển khai hiện tại giữ nguyên.

Luồng dữ liệu: **video gốc → YuNet/crop mặt như runtime → giảm độ phân giải và blur trong train → `prepare_rgb`/`prepare_tensor` dùng chung → fine-tune → chọn bằng validation → xuất PT/ONNX/manifest → kiểm tra video giữ riêng**.

## Thử trước ở cự ly gần và trung bình

**Huấn luyện GPU trên Kaggle:** dataset ZIP và notebook đã được chuẩn bị ở [kaggle_upload/README.md](../../kaggle_upload/README.md). Gói giữ native crop và split; không cần upload video hoặc feature cache. Bản CPU thử trước chưa giữ được kết quả trên clip góc thấp cũ, nên profile mới vẫn là ứng viên thử nghiệm.

Profile riêng `configs/yawn_near_medium_training.yaml` dùng hai clip train đã xem và gán nhãn: `20261010T162711_639383Z.avi` (gần) và `20261010T162914_620331Z.avi` (trung bình). Clip xa không tham gia phiên này. Hai clip vẫn thuộc train; không chuyển một phần frame sang validation để tạo kết quả độc lập giả.

Vì chưa có clip validation camera mới, chế độ `validation_mode: static_only` chọn checkpoint bằng **160 ảnh validation cũ**, tách khỏi 320 ảnh static train và các crop camera train. Kiểm tra hồi quy trên từng nguồn legacy/smiles/GENKI; theo dõi cả F1, ngáp nhầm và recall ngáp tại ngưỡng 0,70. Các clip lỗi đã khóa chỉ được chạy sau khi chốt checkpoint. Đây là ứng viên thử nghiệm; kết quả phát lại clip train chỉ phản ánh mức học dữ liệu đó, chưa chứng minh chất lượng trên video mới/người mới. Không tự thay profile đang dùng.

```powershell
& '.\.venv\Scripts\python.exe' tools/finetune_yawn_distance.py check --config configs/yawn_near_medium_training.yaml
& '.\.venv\Scripts\python.exe' tools/finetune_yawn_distance.py prepare --config configs/yawn_near_medium_training.yaml
& '.\.venv\Scripts\python.exe' tools/finetune_yawn_distance.py train --config configs/yawn_near_medium_training.yaml
```

`prepare`/`train` không ghi đè thư mục đã có dữ liệu. Sau khi đã tạo ứng viên và kiểm tra PT–ONNX, chạy bằng profile `models/yawn_near_medium_candidate/runtime.yaml`. Không dùng các chỉ số static validation để tuyên bố đã đạt tiêu chí camera gần/trung bình. Khi có clip validation mới, chuyển sang `validation_mode: camera` trong một cấu hình có **dataset/output mới**; vẫn có thể giữ `active_distances: [near, medium]`. Quy trình ba cự ly dưới đây tiếp tục là cấu hình mặc định, yêu cầu đầy đủ train/val theo từng cự ly.

## 1. Khởi tạo và quay clip mới

Chạy trong PowerShell tại thư mục `yolov10n`, với môi trường `.venv` hiện có. Dừng `run`/`serve` để nhả camera trước khi quay.

```powershell
& '.\.venv\Scripts\python.exe' tools/finetune_yawn_distance.py init
& '.\.venv\Scripts\python.exe' tools/record_yawn_check.py --source 0 --config configs/camera_usb_robust.yaml --distance near --subject-id p01 --capture-group p01_train_01 --split train --output-dir data_collection/yawn_distance/videos
```

Clip có 5 giây chuẩn bị và 48 giây hướng dẫn: miệng bình thường → ngáp → bình thường → cười nhe răng → bình thường → ngáp → bình thường → nói chuyện → bình thường. Giữ mỗi lần ngáp mô phỏng khoảng 2–3 giây, trở về trạng thái thư giãn giữa các lần. Giữ khoảng cách cố định trong một clip; không ngáp thật khi đang lái xe để thu dữ liệu.

Chạy lại lệnh với `--distance medium`, rồi `--distance far`. Dùng cùng `--capture-group p01_train_01` cho cả ba clip trong cùng buổi thu. Có thể quay thêm nhiều bộ train, ánh sáng/góc đầu/kính khác nhau; đảm bảo miệng khép, cười và ngáp đều có ở mọi cự ly. Không dùng màu áo hay cự ly để phân chia lớp.

Thu **một bộ ba clip mới** cho validation, tốt nhất ở buổi khác: đổi thành `--capture-group p01_val_01 --split val`, lần lượt `near`, `medium`, `far`. Tối thiểu có 6 clip đã gán nhãn: 3 train, 3 val; nên thu 2–3 bộ train. `capture_group` của cùng một buổi không được xuất hiện ở hai split.

`near/medium/far` là nhóm vị trí trong thử nghiệm, chưa phải khoảng cách đã đo bằng centimet. Giữ trọn khuôn mặt; ở cự ly xa mặt vẫn phải đủ lớn để detector nhận. Native crop sẽ được ghi kích thước thật vào dataset. Nếu nhiều frame `no_face` hoặc quá tối/mờ, điều chỉnh vị trí camera/ánh sáng trước khi thu lại.

Thêm `--guide-face-size` để xem chỉ báo kích thước mặt bằng YuNet trên CPU, không nạp classifier. Nếu hiện `MOVE CLOSER`, tiến gần hơn; công cụ chờ kích thước đủ rồi mới đếm ngược 5 giây và ghi. Với profile hiện tại, chỉ báo yêu cầu cạnh ngắn crop mặt khoảng 100 pixel (mặt trước mở rộng phải đạt ngưỡng 80 pixel, có thêm biên dự phòng). `SIZE OK` chỉ xác nhận kích thước; chất lượng `blurry/too_dark` vẫn hiện rõ. Ngưỡng runtime không đổi. Sau khi bắt đầu ghi, clip vẫn giữ cả các frame kém để thấy đúng dữ liệu camera, không bỏ frame cũ rồi nối thời gian.

Không bật `--inspect-model` khi thu train để giảm tải suy luận lúc ghi. AVI **FFV1** giữ nguyên pixel, không có chữ/khung; `.timestamps.json` giữ thời gian thực và hash từng frame; `.protocol.json` giữ người, buổi thu, cự ly, split và fingerprint runtime. Luôn giữ ba file cùng nhau. FPS danh nghĩa của AVI là 30; thời gian đúng nằm trong sidecar.

## 2. Xem và gán nhãn thực tế

Sau mỗi lần quay, thay `TEN_CLIP.avi` dưới đây bằng đường dẫn `Saved:` vừa nhận:

```powershell
& '.\.venv\Scripts\python.exe' tools/annotate_yawn_distance.py --video 'data_collection/yawn_distance/videos/TEN_CLIP.avi'
```

- `Space`: chạy/tạm dừng; `A`/`D`: lùi/tiến 2 giây; `J`/`K`: lùi/tiến một frame.
- `1`: miệng bình thường, `2`: ngáp, `3`: cười, `4`: nói chuyện.
- Chọn loại hành động, đến đầu đoạn nhấn `S`, đến cuối đoạn nhấn `E`. Chỉ đánh dấu khoảng thấy rõ hành động; bỏ khoảng chuyển tiếp chưa xác định.
- `Q`: lưu các đoạn đã đánh dấu vào `annotations.csv`. Đoạn chưa nhấn `E` không được lưu. Clip đã có nhãn không được tự ghi đè.

`smile` và `talk` đều là `no_yawn`; lời nhắc trên màn hình không phải ground truth. Tool dùng thời gian sidecar và xác minh pixel. Không lấy điểm model làm nhãn. Có thể chỉnh lại các khoảng bằng CSV sau khi xem video, dùng đúng `t:...s` trong công cụ này.

CSV có các cột `clip_id,subject_id,capture_group,split,distance,lighting,start,end,label,action,reviewed`; `reviewed=true` chỉ dành cho khoảng đã xem. Không chồng khoảng thời gian. Người/cự ly/buổi thu/ánh sáng/split phải đúng metadata lúc ghi.

## 3. Chuẩn bị crop và fine-tune

```powershell
& '.\.venv\Scripts\python.exe' tools/finetune_yawn_distance.py check
& '.\.venv\Scripts\python.exe' tools/finetune_yawn_distance.py prepare
& '.\.venv\Scripts\python.exe' tools/finetune_yawn_distance.py train
```

Cấu hình nằm ở [`configs/yawn_distance_training.yaml`](../../configs/yawn_distance_training.yaml). Mặc định CPU, 2 thread, batch 16, tối đa 40 epoch, learning rate `1e-4`. Không tải model mới. Giữ lại tối đa 80 ảnh train và 40 ảnh val mỗi nhóm nguồn/lớp từ static records hiện có; chỉ dùng train để tối ưu. Có thể đặt `retained_static_records: null` nếu máy khác không có cache, nhưng khi đó không có kiểm tra hồi quy dataset cũ.

Native crop PNG được lưu trong `.cache/yawn_distance/dataset/native`. Mọi frame được đưa qua Vision trước khi lấy mẫu khoảng 5 frame/s. Dataset lưu cả frame không có crop hoặc chất lượng kém để báo cáo `UNKNOWN` trên validation; các frame này không được âm thầm loại khỏi mẫu số recall. Real crop mờ nhẹ có thể tham gia train nếu vẫn có hình học hợp lệ và Laplacian mặt ≥12, nhưng **runtime tiếp tục giữ ngưỡng 20/6 và xử lý UNKNOWN**. Ngưỡng 12 chỉ là điều kiện chọn mẫu train, không phải thay ngưỡng chạy.

Augmentation mặc định, áp dụng cho cả hai lớp và chỉ cho train:

- 50% lượt lấy mẫu giảm kích thước crop gốc theo hệ số `0,75`, `0,50` hoặc `0,35`, dùng `INTER_AREA`, giữ tỷ lệ hình, cạnh ngắn tối thiểu 24 pixel.
- 25% lượt có Gaussian blur sigma `0,35–0,70`; 15% lượt có motion blur dài 3 pixel. Các phép có thể kết hợp.
- Sau đó dùng **đúng** BGR→RGB, PIL bilinear resize cạnh ngắn, center crop 224×224, chia 255 và normalization từ manifest runtime. Không dùng RandomResizedCrop hay ép crop chữ nhật thành hình vuông.
- Validation/test chỉ dùng crop gốc với cùng preprocessing. Khi chạy thực tế không thêm downsampling/blur.

`augmentation_preview.jpg` cho thấy ảnh rõ và các biến thể. Nếu biến thể làm mất đặc điểm miệng, giảm hệ số/blur trong YAML rồi prepare lại ở thư mục dataset mới. Không dùng dữ liệu synthetic để chứng minh camera xa thực tế đã hoạt động.

Các frame/crop trùng với val/test không được dùng làm train. Clip bị đổi tên vẫn được nhận ra qua checksum. Những clip `20261010T132214_553016Z`, `20261010T133911_739010Z` và `20261010T110453_140956Z` đã khóa sẽ bị từ chối nếu đưa vào train/val.

`split_mode: clip` cho phép một người ở các **clip/buổi khác nhau**, phù hợp giai đoạn phát triển hiện tại; không chứng minh tổng quát hóa sang người mới. Khi thu đủ người, đổi `split_mode: subject`, giữ mọi clip của một người trong cùng split. Static legacy chưa xác định được độc lập theo người và được báo cáo riêng.

Tool kiểm tra cả hai lớp ở cả ba cự ly của train/val. Validation cần ≥10 mẫu dương và âm mỗi cự ly; chọn checkpoint bằng F1 trung bình theo cự ly, đồng thời yêu cầu F1 ≥0,85, recall tại 0,70 kể cả UNKNOWN ≥0,85, tỷ lệ frame âm có điểm ngáp ≥0,70 ≤5%, và kiểm tra không suy giảm static validation. Đây là **điều kiện chọn ứng viên trên frame**, chưa phải nghiệm thu sự kiện/báo nhầm theo giờ.

Nếu không ứng viên nào đạt, chỉ lưu `validation.json`; không xuất weights để chạy. Nếu đạt, lưu `best_yawn.pt`, `best_yawn.onnx`, `manifest.json`, `parity.json`, `runtime.yaml` trong `models/yawn_distance_candidate/`. Kiểm tra PT↔ONNX bằng crop validation thật; nhãn và preprocessing ghi vào manifest. Lệnh train không tự đánh giá test hoặc tự thay model đang dùng. Nếu dataset/đầu ra đã có nội dung, đổi đường dẫn trong YAML cho lần thử tiếp theo; tool không xóa kết quả cũ.

## 4. Kiểm tra các clip lỗi đã giữ riêng

Sau khi có candidate đạt validation:

```powershell
& '.\.venv\Scripts\python.exe' tools/finetune_yawn_distance.py evaluate --manifest models/yawn_distance_candidate/manifest.json --review data_reviews/original_yawn_near_far_locked_check.json --review data_reviews/original_yawn_near_medium_locked_check.json --review data_reviews/usb_camera_lossless_locked_check.json
```

`heldout_evaluation.json` báo kết quả theo hành động và các thời điểm xác nhận của **kênh ngáp** ở tốc độ frame đầy đủ, với EMA/ngưỡng thời gian/chất lượng không đổi. Khoảng không được gán nhãn giữ riêng; clip ngáp mô phỏng ngắn hơn thời gian xác nhận không thể dùng để đòi đủ event recall. Phép kiểm tra này chưa đánh giá kênh mắt/còi, người độc lập hoặc Radxa. Những clip trên là hồi quy đã biết, không dùng để chọn nhiều phiên bản model hay chỉnh hyperparameter liên tục.

Kiểm tra cả hệ thống trên camera hoặc video bằng profile sinh ra:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --config models/yawn_distance_candidate/runtime.yaml --source 0 --backend onnx --display
```

Cần thêm clip test độc lập và đoạn bình thường đủ dài để đo số báo sai/giờ trước khi thay profile PC/Radxa chính. Chưa có phép đo đạt chuẩn nào được suy ra chỉ từ việc setup này.
