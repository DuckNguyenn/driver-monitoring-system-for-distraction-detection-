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

Profile `configs/camera_pc.yaml` hiện dùng `yawn_camera_refined/manifest.json`: checkpoint mắt tham chiếu `eye_refined_v4`, classifier ngáp chỉ huấn luyện lại Linear 1280→2 trên dữ liệu cũ cùng vùng cắt camera có nhãn ngáp/bình thường/cười. Backbone ngáp, hai nhãn và preprocessing không đổi. Xem [sửa bỏ sót ngáp trên video](../reports/YAWN_CAMERA_FIX.md), [sửa mắt](../reports/EYE_CLASSIFIER_FIX.md) và [sửa nhầm cười trước đó](../reports/SMILE_YAWN_FIX.md). Video một người là dữ liệu phát triển, chưa chứng minh nghiệm thu độc lập. Có `.pt` và `.onnx` mới; RKNN trong manifest gốc không đại diện cho các trọng số PC mới.
