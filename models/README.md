# Hợp đồng model

`manifest.json` là nguồn nhãn, preprocessing và checksum cho runtime, converter và evaluator.

| Model | Kiến trúc/nguồn | Đầu vào | Thứ tự lớp |
|---|---|---|---|
| `best_eye.pt` / `.onnx` | Checkpoint cục bộ `camera_classical/best_eye.pt`, YOLOv8n classification, Ultralytics 8.4.163 | RGB 224×224 | 0 Closed, 1 Open |
| `best_yawn.pt` / `.onnx` | Checkpoint cục bộ `camera_classical/best_yawn.pt`, YOLOv8n classification, Ultralytics 8.4.163 | RGB 224×224 | 0 no_yawn, 1 yawn |
| YuNet | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet), `face_detection_yunet_2023mar.onnx` | Frame BGR letterbox 320×320 | Bbox + 5 landmarks |

YuNet commit `47534e27c9851bb1128ccc0102f1145e27f23f98`; SHA256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`; [MIT license](https://github.com/opencv/opencv_zoo/blob/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/LICENSE) đi kèm ở `yunet.LICENSE`. `yunet.source.json` lưu provenance; downloader kiểm tra SHA Git LFS của model trước khi lưu.

Classifiers là model của dự án đã tồn tại trong workspace. Dataset do người dùng cung cấp và các notebook train là nguồn gốc tham khảo; chưa có bằng chứng tách người độc lập cho test ảnh cũ. ONNX được xuất ở opset 12 bằng Torch 2.6.0, ONNX 1.17.0; crop RGB resize cạnh ngắn 224 bằng PIL bilinear, center crop, chia 255, mean=[0,0,0], std=[1,1,1]. Đã so sánh tensor với torchvision và dự đoán với `.pt`.

YuNet dùng CPU. Classifier RKNN nhận RGB `uint8` NHWC; converter nhúng normalization nên adapter không chia 255 hai lần. Hai `.rknn` target `rk3576`, chưa lượng tử hóa, đã tạo bằng SDK 2.3.2 trong Linux x86_64/Python 3.12.10/Torch 2.4.0+cpu. Hash và `conversion_host` nằm trong manifest, bằng chứng ở `../reports/rknn_conversion.json`. Chưa có kết quả NPU; `deployment_validation` còn pending.

`fetch-models` chỉ tải YuNet; `export` dùng checkpoint cục bộ; `convert` chỉ chạy trên Linux. Gói bo chỉ giữ artifact backend được chọn và đường dẫn nằm trong gói. Không suy đoán lớp dựa trên YAML detector cũ hoặc thứ tự thư mục.

Profile `configs/camera_pc.yaml` hiện dùng `yawn_camera_refined/manifest.json`: checkpoint mắt tham chiếu `eye_refined_v4`, classifier ngáp chỉ huấn luyện lại Linear 1280→2 trên dữ liệu cũ cùng vùng cắt camera có nhãn ngáp/bình thường/cười. Backbone ngáp, hai nhãn và preprocessing không đổi. Xem [báo cáo hoàn thiện](../reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.pdf) và [kết quả fine-tune/replay mới nhất](../reports/BLUR_REFINEMENT.md). Video một người là dữ liệu phát triển, chưa chứng minh nghiệm thu độc lập. Có `.pt` và `.onnx` mới; RKNN trong manifest gốc không đại diện cho các trọng số PC mới.

`blur_refined/manifest.json` là bộ model thử được fine-tune bằng ảnh rõ, ảnh mờ thật và Gaussian/motion blur trên crop gốc. Chỉ Linear 1280→2 được cập nhật; extractor được kiểm tra giữ nguyên sau lưu checkpoint. Nhãn, preprocessing và logic xác nhận theo thời gian giữ hợp đồng hiện có. Profile riêng `configs/camera_blur_candidate.yaml` dùng ngưỡng nét mặt/mắt 16/5 đã chọn trên validation thật; profile PC đang dùng vẫn là bản đối chiếu 20/6. [Báo cáo và lệnh chạy](../reports/BLUR_REFINEMENT.md) ghi rõ kết quả phát triển, tỷ lệ UNKNOWN, các trường hợp còn bị chặn và giới hạn dữ liệu. Chưa có RKNN cho bộ trọng số blur; phải chuyển manifest này trên Linux trước khi dùng backend `rknn`.

`yawn_usb_dual_view/manifest.json` là **biến thể suy luận thử**, không phải lần train mới. Manifest v2 tham chiếu nguyên trọng số mắt `eye_refined_v4` và ngáp `yawn_camera_refined`; không chứa bản sao model. Kênh ngáp khai báo `inference_views: [center, edge_pad_square]` và `view_aggregation: max_yawn`. Lượt `center` dùng transform cũ; lượt còn lại thêm viền bằng pixel mép ảnh để tạo hình vuông chứa toàn ROI rồi dùng cùng transform. Điểm hợp nhất là max của hai điểm `yawn`, nhãn `no_yawn` nhận phần bù; điểm này chưa được hiệu chuẩn. Runtime ghi fingerprint khác khi đổi chính sách lượt nhìn, dù checksum trọng số giống nhau. Manifest v1 tiếp tục dùng một lượt như trước.

Biến thể này giữ hồi quy hai đợt ngáp trong clip webcam phát triển và các ảnh validation cũ; ảnh trích bản quay màn hình chỉ dùng chẩn đoán lỗi crop. Sau khi có video USB sạch ngày 09/10, biến thể đạt 1/2 đợt ngáp, chưa đạt hồi quy USB. Giữ `configs/camera_usb_dual_view.yaml` làm bản đối chiếu; không thay profile PC mặc định. [Cách thử và ghi dữ liệu](../README_DRIVER_MONITOR.md#model-ngáp-trên-camera-usb).

`yawn_usb_refined/manifest.json` tham chiếu model mắt cũ và chứa classifier ngáp được fine-tune cục bộ từ `yawn_camera_refined`. Chỉ cập nhật Linear 1280→2; digest xác nhận backbone/conv/BN giữ nguyên sau lưu checkpoint. Model vẫn dùng center crop RGB 224×224, một lượt suy luận, hai nhãn và ngưỡng thời gian cũ. `configs/camera_usb_refined.yaml` chọn bộ trọng số này; PC mặc định vẫn dùng bản đối chiếu.

Dữ liệu USB có nhãn trong `data_reviews/usb_camera_development_labels.json`. Train lấy tối đa 5 frame/s từ đoạn ngáp đầu và các đoạn bình thường/cười; giữ dữ liệu train ảnh cũ. Chọn checkpoint bằng static validation và phát lại các khoảng **validation** qua `Monitor` với ngưỡng 0,70/1 giây, EMA 0,20 giây. Kiểm tra sự kiện theo thời gian thay cho tiêu chí riêng 90% số frame ngáp vượt 0,70; cờ `camera_frame_validation_passed: false` vẫn được ghi rõ trong `evaluation.json`. Đợt ngáp thứ hai và static test không dùng để chọn checkpoint. Clip USB đạt 2/2 đợt sau fine-tune; đây là dữ liệu phát triển cùng người/cùng clip, không phải độ chính xác theo người độc lập. Video webcam cũ cũng giữ 2/2 đợt và không có xác nhận ngáp thừa trong đoạn bình thường/cười. Chưa có RKNN/NPU hoặc xác nhận trực tiếp trên video USB mới sau fine-tune.

Lần thử trực tiếp tiếp theo (`20261009T120313_030301Z`) vẫn bỏ sót ngáp ở góc camera thấp, dù checksum xác nhận đã nạp đúng `yawn_usb_refined`. Đoạn 16–18 giây có 22 frame hợp lệ nhưng điểm thô tối đa 0,1815; tắt EMA không khôi phục được sự kiện. Chưa có video gốc của lần này để phân biệt lỗi vùng cắt với khả năng tổng quát của model. Vì vậy 2/2 trên clip phát triển cũ chưa chứng minh model đã sửa được lỗi trực tiếp; cần giữ đây là bản thử nghiệm.

Recipe tại thư mục dự án:

```powershell
& '.\.venv\Scripts\python.exe' tools/refine_yawn_camera.py prepare --labels data_reviews/usb_camera_development_labels.json --config configs/camera_pc.yaml --cache .cache/yawn_usb_refinement
& '.\.venv\Scripts\python.exe' tools/refine_yawn_camera.py train --labels data_reviews/usb_camera_development_labels.json --config configs/camera_pc.yaml --cache .cache/yawn_usb_refinement --output models/yawn_usb_refined --epochs 150 --camera-weights 0.3 0.5 0.7 --validation-policy events
```

Recipe cần video cá nhân và cache dữ liệu train cũ tại máy; chúng không nằm trong repository. Cache USB tách riêng cache webcam trước đây, kiểm tra checksum video, timestamps, nhãn, manifest và features trước train. `validation.json` lưu thử nghiệm/chọn checkpoint; `evaluation.json` lưu kết quả sau khi khóa model. [Tổng hợp kiểm chứng](../reports/usb_yawn_diagnosis/diagnosis.json).

`yawn_usb_robust/manifest.json` là bản thử tiếp theo, chọn bằng `configs/camera_usb_robust.yaml`. Fine-tune Linear từ `yawn_usb_refined`, giữ nguyên toàn bộ backbone/conv/BN và model mắt. Thêm clip góc thấp `20261009T120936_563235Z.avi`; chỉ các khoảng train trong đợt ngáp đầu/bình thường/cười được tăng cường bằng noise sigma 3/7, Gaussian blur sigma 0,5, JPEG70 và crop lệch 2 pixel. Giữ train ảnh cũ và 42 frame train của clip USB trước. Validation và đợt ngáp thứ hai không có augmentation và không đi vào loss train. Chọn tại camera weight 0,9, L2 0,001, bước 150; guard 90% frame ngáp validation đạt 0,70 và không false positive đều đạt. Kiểm tra lại checkpoint đã lưu: 19/21 frame ngáp validation vượt 0,70, xác nhận đúng một sự kiện bằng Monitor, không xác nhận ngáp trong các khoảng validation âm tính.

Ba lượt phát lại phát triển giữ 2/2 đợt mỗi clip, không có đợt ngáp thừa trong các khoảng bình thường/cười đã đánh dấu. Tuy nhiên clip góc thấp phát triển dùng MJPG: chính model cũ nhận 1/2 theo probe lúc quay nhưng 2/2 khi giải mã. Kết quả decoded của bản robust chỉ là hồi quy phát triển; không trình bày 6/6 trên ba clip như recall độc lập. Bộ ngưỡng nét, ngưỡng ngáp 0,70/1 giây và EMA 0,20 giây giữ nguyên; không thêm lượt suy luận hoặc bộ lọc ảnh ở runtime. Chưa chuyển RKNN của bộ trọng số này.

Kiểm tra FFV1 mới ngày 10/10 (`20261010T110453_140956Z.avi`) xác minh cả 424 frame/ảnh RGB224/bbox/điểm ngáp trùng dữ liệu lúc quay. Model robust nhận 1/2 đợt đã xem, xác nhận đợt thứ hai ở 29,891 s; đợt đầu chỉ giữ điểm sau EMA ≥0,70 trong 0,890 s. Không đếm ngáp trong các khoảng bình thường/cười đã đánh dấu. `evaluation.json` ghi rõ chưa đạt kiểm tra camera này. Video mới được giữ ngoài train/chọn checkpoint; nhãn kiểm tra ở `data_reviews/usb_camera_lossless_locked_check.json`. Cùng người phát triển nên vẫn chưa chứng minh tách người độc lập. [Biểu đồ](../reports/usb_yawn_diagnosis/usb_lossless_check.png).

Static test sau khóa model: macro-F1 legacy face 0,9809 → 0,9763; legacy full 0,9953 → 0,9860. Tập âm tính cười chuyên biệt có 0/582 ảnh vượt 0,70; GENKI có 3/316 ảnh vượt 0,70 so với 0/316 của bản trước. Đây là đánh đổi cần theo dõi bằng hoạt động bình thường dài giờ; chưa có bằng chứng đạt mục tiêu báo nhầm theo giờ.

```powershell
& '.\.venv\Scripts\python.exe' tools/refine_yawn_camera.py prepare --labels data_reviews/usb_camera_low_angle_development_labels.json --config configs/camera_usb_refined.yaml --cache .cache/yawn_usb_robust --augment
& '.\.venv\Scripts\python.exe' tools/refine_yawn_camera.py train --labels data_reviews/usb_camera_low_angle_development_labels.json --config configs/camera_usb_refined.yaml --cache .cache/yawn_usb_robust --retain-camera-cache .cache/yawn_usb_refinement --output models/yawn_usb_robust --epochs 300 --camera-weights 0.8 0.9 --validation-policy frames
```

Ứng viên `yawn_near_medium_candidate` được train thử từ hai clip gần/trung bình, native downsampling và blur nhẹ; chỉ Classify conv/BN affine/Linear thay đổi. Chọn epoch 21 bằng 160 ảnh static validation, PT–ONNX đối chiếu đạt. Hai clip train có 4/4 đợt được xác nhận, nhưng clip USB góc thấp giữ riêng bị bỏ sót; chưa thay profile mặc định. [Gói dataset + notebook Kaggle GPU](../kaggle_upload/README.md) dùng lại crop/split, cung cấp cả checkpoint ban đầu và USB refined, xuất gói PT/ONNX/profile riêng `yawn_kaggle_near_medium`; chưa có kết quả GPU Kaggle quan sát trực tiếp.
