# Ảnh hồi quy cục bộ

Các ảnh khuôn mặt dùng để tái hiện lỗi mắt/ngáp/cười và video camera cá nhân không được đưa lên GitHub. Model và test code vẫn được cung cấp. Khi thiếu những ảnh này, unittest bỏ qua riêng các ca cần ảnh và ghi lý do; không tạo kết quả suy luận giả để thay thế.

Trong bản dự án đầy đủ tại máy, các thư mục `eyes/`, `eye_motion/`, `smiles/`, `yawns/` chứa ảnh cùng `source.json` mô tả nguồn/checksum. Hai ca trong `test_models_vision.py` và một ca trong `test_smile_classifier.py` còn dùng ảnh `kaggle_output/data/yawn_dataset/images/test/yawn__100__749ff8f0.jpg`. Cần phục hồi đúng ảnh gốc/checksum để chạy lại những ca đã biết; thay ảnh tùy ý không tái hiện được phép kiểm thử đó.

Dữ liệu gốc và quy trình thu mới được mô tả trong [data_collection/README.md](../../data_collection/README.md), [data_reviews/README.md](../../data_reviews/README.md) và các báo cáo sửa lỗi. Có thể chạy các test logic/capture/serial độc lập mà không tải các bộ ảnh này.
