# Model ngáp bổ sung ảnh cười

Đây là model sửa nhầm cười trước khi có video camera ngáp ngày 07/10/2026; model được giữ để đối chiếu. Profile PC hiện đã chuyển sang `../yawn_camera_refined/manifest.json` để sửa bỏ sót ngáp trên camera. Bản trong thư mục này giữ backbone YOLOv8n classification và preprocessing RGB 224×224; huấn luyện lại Linear 1280→2 với ảnh cười có nhãn `no_yawn`. Model mắt và YuNet giữ nguyên.

`manifest.json` quy định nhãn, preprocessing, checksum và nguồn artifact. `validation.json` lưu lựa chọn bằng validation; `evaluation.json` lưu đánh giá test sau khi chốt weights. Xem [báo cáo kiểm thử và nguồn dữ liệu](../../reports/SMILE_YAWN_FIX.md).

Có PyTorch và ONNX; chưa có RKNN cho weights mới. Tập ảnh phát triển chưa chứng minh độc lập theo người hoặc nghiệm thu sự kiện camera.
