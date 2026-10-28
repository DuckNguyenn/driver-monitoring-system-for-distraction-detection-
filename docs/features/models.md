# Model và profile

## Kiến trúc đang sử dụng

YuNet phát hiện mặt/mốc trên CPU. Hai model mắt và ngáp là YOLOv8n classification, không phải
object detector. Input 224×224; đọc xác suất theo tên lớp từ manifest, không giả định chỉ số.
Nhãn profile đang chọn: mắt `Closed`, `Open`; ngáp `no_yawn`, `yawn`.
Preprocessing RGB, resize cạnh ngắn/center crop, bilinear và normalization theo manifest.

## Phân biệt các profile

| Vai trò | Nguồn chọn |
|---|---|
| Mặc định serve trên PC | `configs/camera_pc.yaml`; hiện tham chiếu yawn_camera_refined |
| Profile người dùng chọn gần nhất | `models/yawn_kaggle_near_medium/runtime.yaml` |
| Mắt của profile trên | `models/eye_refined_v4/best_eye.onnx` |
| Ngáp của profile trên | `models/yawn_kaggle_near_medium/best_yawn.onnx` |
| Auto-glasses | Opt-in, nhánh riêng; xem [glasses](glasses.md) |
| Model trong ZIP Radxa hiện dùng | `models/eye.onnx`, `models/yawn.onnx`, manifest portable của near/medium |

Hash ONNX profile near/medium:

- Eye: `165e8cf94e0283135d6f4cb1c799261c47c5b6aca4501cbc43b98a7d66e5e6ed`.
- Yawn: `9834d3a39a176622bfdbbe51b4d74aab7bbbe23a3a57ec9d1acddbf3e5ff6af6`.

Các file near/medium có thể bị Git ignore và chỉ có ở máy hiện tại/bộ đóng gói; clone mới cần
nhận artifact đúng hash trước khi chạy. Model RKNN nền cũ khác model này.

## Quy tắc sửa

- Đổi preprocessing/crop/backend phải đo parity nhãn/xác suất và ảnh hưởng F1.
- Fine-tune vào thư mục candidate riêng; chọn bằng validation, không chọn bằng test.
- Cập nhật hash/manifest đồng bộ với file thực. Không thay model mặc định do một ca demo.
- RKNN của model đang chọn phải được chuyển riêng cho rk3576; xem [radxa](radxa.md).

## Kiểm tra

```bash
python -m unittest tests.test_models_vision tests.test_eye_classifier -v
```

[Nguồn/giấy phép model](../../models/README.md), [hướng dẫn đầy đủ](../../README_DRIVER_MONITOR.md).
