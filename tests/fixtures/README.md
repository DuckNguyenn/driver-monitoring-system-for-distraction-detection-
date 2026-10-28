# Ảnh hồi quy cục bộ

Các ảnh khuôn mặt dùng để tái hiện lỗi mắt/ngáp/cười và video camera cá nhân không được đưa lên GitHub. Model và test code vẫn được cung cấp. Khi thiếu những ảnh này, unittest bỏ qua riêng các ca cần ảnh và ghi lý do; không tạo kết quả suy luận giả để thay thế.

Trong bản dự án đầy đủ tại máy, các thư mục `eyes/`, `eye_motion/`, `smiles/`, `yawns/` chứa ảnh cùng `source.json` mô tả nguồn/checksum. Hai ca trong `test_models_vision.py` và một ca trong `test_smile_classifier.py` còn dùng ảnh `kaggle_output/data/yawn_dataset/images/test/yawn__100__749ff8f0.jpg`. Cần phục hồi đúng ảnh gốc/checksum để chạy lại những ca đã biết; thay ảnh tùy ý không tái hiện được phép kiểm thử đó.

`usb_yawn/` chứa ba crop trích từ bản quay màn hình ngày 09/10/2026 và `source.json` ghi SHA256, thời điểm, phạm vi. Test `test_yawn_usb_views.py` dùng chúng để hồi quy chính sách crop và kiểm tra tương đương Torch/ONNX. Ảnh còn overlay/nén, không phải frame camera gốc; ca test này không chứng minh recall sự kiện USB và không cung cấp dữ liệu train. Các test hợp đồng manifest, giữ bằng chứng của lượt cũ và fingerprint vẫn chạy khi thiếu ảnh cá nhân.

`usb_camera/` chứa năm ROI mặt trích theo thời điểm đã chọn trước khi train hoàn tất từ video USB sạch `20261009T105555_466558Z.avi`: bình thường, cười, ngáp đầu và ngáp thứ hai. `source.json` giữ checksum video/timestamps/PNG/tensor đầu vào cùng frame, thời điểm và bbox. `test_yawn_usb_classifier.py` kiểm tra classifier mới, âm tính cười, Torch/ONNX và giữ model mắt/ngưỡng cũ. Đây là hồi quy ảnh trên clip phát triển, không thay thế phát lại toàn video hay kiểm thử độc lập. Test chọn checkpoint theo thời gian ở `test_yawn_training_validation.py` chạy được không cần ảnh cá nhân.

`usb_low_angle/` lưu năm ROI ở các thời điểm 4/8/12/19/33 giây của clip góc thấp `20261009T120936_563235Z.avi`. Test `test_yawn_usb_robust.py` tái hiện mẫu ngáp hở răng bị âm tính, kiểm tra nhiễu nhẹ, cười âm tính, parity và ngưỡng/model mắt. Clip này nén MJPG, nên các pixel fixture chỉ dùng hồi quy decoded, không đại diện nguyên pixel lúc camera chạy trực tiếp. Bộ ghi đã đổi sang FFV1 với hash từng frame và từng đầu vào classifier; vẫn cần ghi mới để kiểm chứng camera trực tiếp.

Dữ liệu gốc và quy trình thu mới được mô tả trong [data_collection/README.md](../../data_collection/README.md), [data_reviews/README.md](../../data_reviews/README.md) và các báo cáo sửa lỗi. Có thể chạy các test logic/capture/serial độc lập mà không tải các bộ ảnh này.
