# Model ngáp hiệu chỉnh bằng video camera

Profile PC hiện dùng `manifest.json` trong thư mục này. YuNet, checkpoint mắt `eye_refined_v4` và preprocessing RGB 224×224 giữ nguyên. Classifier ngáp vẫn là YOLOv8n classification, hai lớp `no_yawn, yawn`. Chỉ Linear 1280→2 được huấn luyện lại; backbone, convolution/BatchNorm của Classify giữ nguyên.

Dữ liệu bổ sung lấy từ vùng cắt YuNet trong video `20261007T070644_475102Z.avi`. Giữ dữ liệu train mắt ngáp/cười cũ, bổ sung ngáp, cười và trạng thái bình thường trên camera. Mẫu train camera lấy cách nhau ít nhất 0,2 giây. Lần ngáp thứ hai không tham gia huấn luyện hoặc chọn model. Validation dùng ảnh cũ và các đoạn riêng trong lần ngáp đầu; các đoạn vẫn cùng người/cùng clip nên có tương quan.

`validation.json` lưu mọi thử nghiệm và lựa chọn; `evaluation.json` lưu kết quả test ảnh và lần ngáp thứ hai sau khi khóa checkpoint. Manifest quy định tên lớp, preprocessing và checksum. Có `.pt` và `.onnx`; chưa chuyển RKNN cho trọng số mới.

Phát lại video bằng ONNX: 2/2 lần ngáp được xác nhận, đoạn cười không tạo sự kiện ngáp. Đây là kiểm thử phát triển một người, chưa phải nghiệm thu độc lập. [Báo cáo đầy đủ](../../reports/YAWN_CAMERA_FIX.md) có số đo, giới hạn và lệnh tái hiện.

Tái tạo từ cấu hình trước sửa, xuất sang thư mục mới:

```powershell
& '.\.venv\Scripts\python.exe' tools/refine_yawn_camera.py prepare --config configs/camera_yawn_previous.yaml
& '.\.venv\Scripts\python.exe' tools/refine_yawn_camera.py train --config configs/camera_yawn_previous.yaml --output models/yawn_camera_reproduced
```

Cần video/sidecar/nhãn còn nguyên và cache static của `tools/refine_yawn_head.py`. Hash dữ liệu được kiểm tra trước khi train. Không ghi đè model gốc, checkpoint mắt hoặc manifest RKNN cũ.
