# Hình tham khảo cho báo cáo giám sát tài xế

Ngày chọn nguồn: 24/10/2026.

Bộ sưu tập chọn theo cách trình bày của báo cáo mẫu: ảnh thật, ảnh trước–sau xử lý, hình giải thích từng phép tính và ảnh phần cứng có chú giải.

## Cách dùng hình học từ báo cáo mẫu

Báo cáo mẫu đặt hình ngay sau đoạn giải thích: ảnh tách biên (trang PDF 22), bộ phân loại và đặc trưng (30), mốc khuôn mặt (35), bo và camera (44–45). Sơ đồ hệ thống ở trang 59 dùng ảnh thiết bị nối bằng mũi tên; trang 60 dùng lưu đồ hoạt động.

Áp dụng cho DA2: thêm ảnh thật cạnh hình nguyên lý để người đọc thấy đầu vào và kết quả. Mỗi hình có một ý chính, đoạn dẫn trước hình và chú thích nguồn phía dưới.

Các hình này là tư liệu tham khảo. Hình kiến trúc YuNet/YOLOv8n, luồng Monitor, trạng thái và giao tiếp còi vẫn cần phản ánh đúng DA2. Sơ đồ hệ thống có thể phối hợp ảnh ROCK 4D/ESP32 với luồng Camera → xử lý → cảnh báo, nhật ký và web.

Giữ các mục chưa có nội dung ở trạng thái trống. Ảnh sản phẩm không dùng thay ảnh lắp ráp hay kết quả thực nghiệm. Bản Word hiện hành chưa được thay đổi trong lượt tìm hình này.

## Danh sách hình đã tải

### 01. YuNet trên khuôn mặt thật (ưu tiên)

Vị trí: **2.2.3. Nguyên lý phát hiện khuôn mặt bằng YuNet**. Kích thước: 640 × 480 px.

[Ảnh đã tải](../report_assets/web_references_20261024/01_yunet.gif) · [Trang nguồn](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)

Chú thích đề xuất: Ví dụ phát hiện hộp mặt và năm điểm mốc bằng YuNet. Nguồn: OpenCV Zoo.

Dùng để thấy đầu ra detector. FPS trong ảnh thuộc ví dụ của nguồn, không phải phép đo DA2.

Ghi nguồn: MIT theo LICENSE của thư mục YuNet.

### 02. YuNet phát hiện nhiều khuôn mặt (dự phòng)

Vị trí: **2.2.3. YuNet**. Kích thước: 2048 × 1150 px.

[Ảnh đã tải](../report_assets/web_references_20261024/02_yunet_many_faces.jpg) · [Trang nguồn](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)

Chú thích đề xuất: Ví dụ nhiều hộp mặt trong một ảnh. Nguồn: OpenCV Zoo.

Chỉ minh họa detector; hệ thống DA2 chọn một tài xế và xử lý trường hợp nhiều mặt riêng.

Ghi nguồn: MIT theo LICENSE của thư mục YuNet.

### 03. Ảnh gốc và ảnh bị làm mờ (ưu tiên)

Vị trí: **2.1.4. Chất lượng ảnh**. Kích thước: 450 × 283 px.

[Ảnh đã tải](../report_assets/web_references_20261024/03_gaussian.jpg) · [Trang nguồn](https://docs.opencv.org/4.x/d4/d13/tutorial_py_filtering.html)

Chú thích đề xuất: So sánh ảnh gốc với ảnh sau lọc Gaussian. Nguồn: OpenCV, Smoothing Images.

Giải thích mất chi tiết khi ảnh mờ. Không dùng hình này như kết quả kiểm thử mắt của DA2.

Ghi nguồn: Ghi nguồn OpenCV; chưa xác minh giấy phép riêng của ảnh.

### 04. Từ ảnh đầu vào đến điểm số phân loại (ưu tiên)

Vị trí: **2.8.4. Nguyên lý mạng nơ-ron tích chập**. Kích thước: 1255 × 601 px.

[Ảnh đã tải](../report_assets/web_references_20261024/04_cnn.jpeg) · [Trang nguồn](https://cs231n.github.io/convolutional-networks/)

Chú thích đề xuất: Ví dụ các lớp xử lý trong một mạng tích chập. Nguồn: CS231n.

Sơ đồ CNN khái quát; kiến trúc YOLOv8n thực tế vẫn dùng hình kiểm kê hiện có.

Ghi nguồn: Ghi nguồn CS231n; chưa xác minh giấy phép riêng của ảnh.

### 05. Ví dụ các bộ lọc đã học (dự phòng)

Vị trí: **2.8.4. Nguyên lý CNN**. Kích thước: 627 × 248 px.

[Ảnh đã tải](../report_assets/web_references_20261024/05_filters.jpeg) · [Trang nguồn](https://cs231n.github.io/convolutional-networks/)

Chú thích đề xuất: Ví dụ trực quan hóa các bộ lọc ở lớp đầu. Nguồn: CS231n.

Các trọng số thuộc ví dụ mạng của nguồn, không phải trọng số hai classifier DA2.

Ghi nguồn: Ghi nguồn CS231n; chưa xác minh giấy phép riêng của ảnh.

### 06. Bước trượt của bộ lọc (ưu tiên)

Vị trí: **2.8.4. Nguyên lý CNN**. Kích thước: 861 × 172 px.

[Ảnh đã tải](../report_assets/web_references_20261024/06_stride.jpeg) · [Trang nguồn](https://cs231n.github.io/convolutional-networks/)

Chú thích đề xuất: Minh họa stride và vị trí bộ lọc trên đầu vào. Nguồn: CS231n.

Dùng cạnh phần giải thích stride, chỉ chọn nếu chữ đủ rõ ở khổ in.

Ghi nguồn: Ghi nguồn CS231n; chưa xác minh giấy phép riêng của ảnh.

### 07. Phép lấy giá trị lớn nhất trong vùng (dự phòng)

Vị trí: **2.8.7. YuNet và các khối xử lý**. Kích thước: 787 × 368 px.

[Ảnh đã tải](../report_assets/web_references_20261024/07_maxpool.jpeg) · [Trang nguồn](https://cs231n.github.io/convolutional-networks/)

Chú thích đề xuất: Ví dụ max pooling với cửa sổ 2 × 2. Nguồn: CS231n.

Max pooling khác global average pooling ở đầu phân loại YOLOv8n; không gắn nhầm hai khối.

Ghi nguồn: Ghi nguồn CS231n; chưa xác minh giấy phép riêng của ảnh.

### 08. Hoạt ảnh bộ lọc trượt (ưu tiên)

Vị trí: **2.8.4. Nguyên lý CNN**. Kích thước: 244 × 259 px.

[Ảnh đã tải](../report_assets/web_references_20261024/08_convolution.gif) · [Trang nguồn](https://github.com/vdumoulin/conv_arithmetic)

Chú thích đề xuất: Tích chập không đệm, bước trượt một. Nguồn: Vincent Dumoulin và Francesco Visin.

GIF xem chuyển động; khi đưa vào Word dùng một khung hình rõ hoặc chuỗi khung có chú thích.

Ghi nguồn: MIT; ghi tên tác giả và A guide to convolution arithmetic for deep learning.

### 09. Ảnh thật bo ROCK 4D (ưu tiên)

Vị trí: **2.5.3. Máy tính nhúng Radxa ROCK 4D**. Kích thước: 1200 × 800 px.

[Ảnh đã tải](../report_assets/web_references_20261024/09_rock4d.webp) · [Trang nguồn](https://docs.radxa.com/en/rock4/rock4d)

Chú thích đề xuất: Mặt trên bo Radxa ROCK 4D. Nguồn: Radxa Docs.

Ảnh sản phẩm của hãng, không phải ảnh bộ thiết bị đã lắp trong đề tài.

Ghi nguồn: CC BY 4.0 theo footer Radxa Docs.

### 10. Các cổng và thành phần trên ROCK 4D (ưu tiên)

Vị trí: **2.5.3. Máy tính nhúng Radxa ROCK 4D**. Kích thước: 949 × 1081 px.

[Ảnh đã tải](../report_assets/web_references_20261024/10_rock4d_ports.webp) · [Trang nguồn](https://docs.radxa.com/en/rock4/rock4d)

Chú thích đề xuất: Vị trí các cổng và thành phần trên ROCK 4D. Nguồn: Radxa Docs.

Kèm chú giải các số cần dùng: nguồn, USB, Ethernet, SoC; đối chiếu phiên bản bo khi mô tả thiết bị thực.

Ghi nguồn: CC BY 4.0 theo footer Radxa Docs.

### 11. ESP32 DevKitC có chú giải thành phần (ưu tiên)

Vị trí: **2.7.1. Giới thiệu ESP32**. Kích thước: 1738 × 751 px.

[Ảnh đã tải](../report_assets/web_references_20261024/11_esp32.png) · [Trang nguồn](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html)

Chú thích đề xuất: Các thành phần của ESP32-DevKitC V4. Nguồn: Espressif.

Ảnh bo phát triển tham khảo. Chưa xác nhận bo ESP32 lắp thực tế là đúng biến thể DevKitC V4.

Ghi nguồn: Ghi nguồn Espressif; chưa xác minh giấy phép riêng của ảnh.

### 12. Sơ đồ chân ESP32 DevKitC V4 (dự phòng)

Vị trí: **2.7.2. Cấu hình giao tiếp**. Kích thước: 1600 × 1091 px.

[Ảnh đã tải](../report_assets/web_references_20261024/12_esp32_pinout.png) · [Trang nguồn](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html)

Chú thích đề xuất: Sơ đồ chân ESP32-DevKitC V4. Nguồn: Espressif.

Chỉ dùng với chú thích đúng biến thể. Sơ đồ dây DA2 vẫn thể hiện GPIO25, driver còi và mass chung.

Ghi nguồn: Ghi nguồn Espressif; chưa xác minh giấy phép riêng của ảnh.
