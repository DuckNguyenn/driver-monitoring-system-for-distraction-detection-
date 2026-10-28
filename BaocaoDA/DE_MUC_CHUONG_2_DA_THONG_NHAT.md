# Đề mục Chương 2 đã thống nhất

Cập nhật ngày 25/10/2026 theo bản người dùng chỉnh sửa.

Bản review hiện hành cục bộ: `Chuong2_test.docx` (có ảnh mặt, không kèm bản GitHub). Đã cập nhật trực tiếp, giữ phần lý thuyết và cả 7 ảnh nhúng người dùng bổ sung.

## Mạch nội dung

Khái niệm điểm ảnh và ảnh số → các công đoạn xử lý ảnh → tiền xử lý và nội suy → ROI và chất lượng → phát hiện khuôn mặt → phân loại bằng CNN → xử lý thông tin theo thời gian. Các phần phần cứng, công cụ và chỉ số đánh giá tiếp nối bằng đoạn dẫn giải.

Nội suy là ước lượng giá trị điểm ảnh, không đồng nhất với diễn giải ngữ nghĩa. Phân đoạn, phân loại và phát hiện được phân biệt theo dạng đầu ra. Nội dung vẫn là cơ sở lý thuyết, không trình bày cấu hình hoặc luật riêng của hệ thống.

## Đề mục trong bản Word

### 2.1 Tổng quan về xử lý ảnh

- 2.1.1 Điểm ảnh và độ phân giải
- 2.1.2 Ảnh số và các dạng biểu diễn
- 2.1.3 Các bước cơ bản trong xử lý ảnh
  - 2.1.3.1 Thu nhận ảnh
  - 2.1.3.2 Tiền xử lý ảnh
  - 2.1.3.3 Phân đoạn hoặc phân vùng ảnh
  - 2.1.3.4 Biểu diễn và trích chọn đặc trưng
  - 2.1.3.5 Nhận dạng và phân loại ảnh
  - 2.1.3.6 Cơ sở tri thức
- 2.1.4 Tiền xử lý và nội suy ảnh
- 2.1.5 Vùng ảnh quan tâm ROI
- 2.1.6 Đánh giá chất lượng ảnh
### 2.2 Phát hiện khuôn mặt và xác định điểm mốc

- 2.2.1 Phát hiện khuôn mặt bằng YuNet
- 2.2.2 Điểm mốc khuôn mặt và khoảng cách Euclid
- 2.2.3 IoU và loại bỏ hộp trùng
- 2.2.4 Letterbox và biến đổi tọa độ
### 2.3 Mạng nơ-ron tích chập và phân loại ảnh

- 2.3.1 Nguyên lý mạng nơ-ron tích chập
- 2.3.2 Mô hình YOLOv8n classification
- 2.3.3 Hàm Softmax và xác suất lớp
- 2.3.4 Huấn luyện và học chuyển giao
### 2.4 Phương pháp xử lý thông tin theo thời gian

- 2.4.1 Chuỗi quan sát và đặc trưng thời gian
- 2.4.2 Thời lượng nhắm mắt và chu kỳ chớp mắt
- 2.4.3 Bộ lọc EMA và nguyên lý hysteresis
- 2.4.4 Máy trạng thái hữu hạn
### 2.5 Thiết bị phần cứng

- 2.5.1 Camera và nguyên lý tạo ảnh
- 2.5.2 Thông số kỹ thuật camera rời
- 2.5.3 Máy tính nhúng Radxa ROCK 4D
- 2.5.4 Vi điều khiển ESP32 và còi
### 2.6 Ngôn ngữ, công cụ và định dạng mô hình

- 2.6.1 Python và các thư viện
- 2.6.2 Định dạng mô hình và bộ thực thi
- 2.6.3 Giao thức truyền dữ liệu và lưu trữ
### 2.7 Các chỉ số đánh giá

- 2.7.1 Đánh giá phân loại ảnh
- 2.7.2 Đánh giá sự kiện và hiệu năng

## Tình trạng review

15 trang, 11 hình, 12 công thức (8 công thức Word và 4 ảnh công thức được giữ), 29 nguồn tham khảo. Đã xem đủ 15 trang; nội dung trống tại 2.5.2 được giữ nguyên.

Các bản NGAN_GON và CHINH_LY trước được giữ để đối chiếu. Chưa ghép vào báo cáo đầy đủ hoặc sửa Chương 3–5. Bản trước khi sửa được lưu tại `.cache/chapter2-test-flow/Chuong2_test.before.docx`.
