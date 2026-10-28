# CHƯƠNG 4 THI CÔNG VÀ TRIỂN KHAI HỆ THỐNG

Đề mục đề xuất ngày 25/10/2026, tiếp nối Chương 3 hiện hành. Chương này trình bày cách xây dựng, lắp ráp, lập trình và đưa hệ thống vào vận hành. Các số đo độ chính xác, tốc độ xử lý và độ trễ thuộc Chương 5.

## 4.1 Chuẩn bị thi công

### 4.1.1 Thiết bị và linh kiện sử dụng
### 4.1.2 Công cụ và môi trường phát triển phần mềm

## 4.2 Thi công và lắp ráp phần cứng

### 4.2.1 Lắp đặt và kết nối camera USB
### 4.2.2 Lắp ráp khối cảnh báo ESP32-WROOM-32 và buzzer
### 4.2.3 Kết nối các khối và kiểm tra nguồn cấp

## 4.3 Chuẩn bị dữ liệu và huấn luyện mô hình

### 4.3.1 Thu thập, tổ chức và phân chia dữ liệu
### 4.3.2 Huấn luyện và hiệu chỉnh mô hình nhận diện mắt
### 4.3.3 Huấn luyện và hiệu chỉnh mô hình nhận diện ngáp
### 4.3.4 Xuất mô hình và quản lý trọng số

## 4.4 Xây dựng phần mềm giám sát và cảnh báo

### 4.4.1 Lập trình thu nhận và xử lý ảnh
### 4.4.2 Tích hợp các mô hình nhận diện
### 4.4.3 Lập trình xác nhận sự kiện và quyết định cảnh báo
### 4.4.4 Lập trình ESP32 và giao tiếp với Radxa
### 4.4.5 Lập trình ghi nhật ký và lưu trữ lịch sử

## 4.5 Xây dựng giao diện web

### 4.5.1 Xây dựng dịch vụ cung cấp dữ liệu
### 4.5.2 Xây dựng màn hình giám sát trực tiếp
### 4.5.3 Xây dựng chức năng tra cứu lịch sử và xuất dữ liệu

## 4.6 Triển khai trên Radxa ROCK 4D

### 4.6.1 Cài đặt môi trường và đóng gói chương trình
### 4.6.2 Cấu hình camera, mô hình và kết nối ESP32
### 4.6.3 Tích hợp và kiểm tra luồng hoạt động

## 4.7 Quy trình vận hành hệ thống

### 4.7.1 Chuẩn bị và khởi động phiên giám sát
### 4.7.2 Theo dõi cảnh báo và xem lịch sử
### 4.7.3 Dừng hệ thống và xử lý sự cố cơ bản

---

Ghi chú khi triển khai nội dung:

- Kiến trúc, lý do lựa chọn và luật xử lý đã trình bày ở Chương 3; Chương 4 mô tả các bước thực hiện cùng hình ảnh, cấu hình và phần chương trình liên quan.
- Hệ thống sử dụng Radxa ROCK 4D, camera USB và ESP32-WROOM-32 điều khiển buzzer. Báo cáo không đưa PC, app mobile, GPS hoặc Tailscale vào phương án triển khai.
- Chỉ viết nội dung thi công có bằng chứng tương ứng. Các bước chưa thực hiện giữ trống; không mô tả việc chạy NPU hoặc lắp đặt cabin như đã hoàn tất khi chưa có kiểm chứng.
- Đây là đề mục đề xuất; chưa chèn nội dung hoặc sửa các file Word.
