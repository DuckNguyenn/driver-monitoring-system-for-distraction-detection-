# Đánh giá đề mục phần xử lý ảnh Chương 2

Ngày: 24/10/2026.

Phạm vi chính: mục 2.1 trong [báo cáo hiện hành](../reports/BAO_CAO_GIAM_SAT_BUON_NGU_CHINH_SUA.md), đối chiếu thêm mục 2.2–2.3 để tránh trùng nội dung.
Đã có hai đánh giá độc lập về cấu trúc trình bày và ranh giới kỹ thuật, sau đó trao đổi để thống nhất đề xuất dưới đây.
Đây là đề xuất bố cục, chưa sửa nội dung hoặc đánh số trong báo cáo Word.

## Kết luận

Các đề mục hiện tại cơ bản phù hợp, nhưng một số tên còn chung hoặc hẹp hơn nội dung.
Nên giữ năm tiểu mục, đổi tên cho rõ và tách phần lý thuyết khỏi thông số triển khai cụ thể.

| Mục | Tên hiện tại | Tên đề xuất | Nhận xét |
| --- | --- | --- | --- |
| 2.1 | Tổng quan về xử lý ảnh | Cơ sở xử lý ảnh số | Bao quát các khái niệm và thao tác nền tảng cần cho các phần sau. |
| 2.1.1 | Giới thiệu xử lý ảnh | Ảnh số và biểu diễn ảnh | Nêu rõ nội dung điểm ảnh, độ phân giải, ảnh màu và thứ tự kênh. |
| 2.1.2 | Các bước cơ bản trong xử lý ảnh | Giữ nguyên | Cần trình bày quy trình khái quát; bản hiện tại đang mô tả khá cụ thể chuỗi xử lý DA2. |
| 2.1.3 | Vùng ảnh quan tâm | Vùng ảnh quan tâm (ROI) | Giữ nội dung và bổ sung thuật ngữ viết tắt để dùng nhất quán. |
| 2.1.4 | Chất lượng ảnh | Đánh giá chất lượng ảnh | Đúng với nội dung đo độ sáng, độ nét, vùng quá sáng và kích thước vùng quan sát. |
| 2.1.5 | Nội suy và chuẩn hóa đầu vào | Tiền xử lý ảnh đầu vào | Bao quát đổi thứ tự kênh, thay đổi kích thước, nội suy, cắt giữa và chuẩn hóa. |

## Bộ đề mục thống nhất

**2.1. Cơ sở xử lý ảnh số**

- **2.1.1. Ảnh số và biểu diễn ảnh**
- **2.1.2. Các bước cơ bản trong xử lý ảnh**
- **2.1.3. Vùng ảnh quan tâm (ROI)**
- **2.1.4. Đánh giá chất lượng ảnh**
- **2.1.5. Tiền xử lý ảnh đầu vào**

## Ranh giới nội dung khi viết

- Mục 2.1.1 giải thích ảnh số và kênh màu. BGR/RGB là thứ tự kênh; tránh trình bày thành hai không gian màu khác nhau.
- Mục 2.1.2 dùng một sơ đồ quy trình khái quát, nêu các bước tùy nhiệm vụ; tránh coi chuỗi xử lý riêng của DA2 là trình tự bắt buộc cho mọi hệ thống.
- Mục 2.1.3 giải thích khái niệm và việc chọn vùng quan sát. Mục 2.1.5 giải thích chuẩn bị vùng ảnh đó cho đầu vào mô hình; phân biệt chọn ROI với cắt giữa trong tiền xử lý.
- Mục 2.1.4 trình bày ý nghĩa và nguyên lý các phép đo chất lượng. Giữ công thức cần thiết, đưa ngưỡng và thông số cấu hình riêng sang Chương 3–4.
- Mục 2.1.5 trình bày nguyên lý. Chi tiết kích thước 320/224, mean/std, profile và backend thuộc phần thiết kế hoặc triển khai tương ứng. Mục 2.8.3 chỉ dẫn lại nguyên lý tiền xử lý và giải thích xác suất đầu ra để tránh lặp.
- Các đề mục hiện còn trống trong báo cáo vẫn để trống; đề xuất này không bổ sung nội dung cho các mục đó.

## Hai điều chỉnh liên quan

1. Đổi **2.2. Giải thuật Facial Landmarks** thành **2.2. Phát hiện khuôn mặt và xác định điểm mốc**. Điểm mốc là khái niệm/đầu ra; YuNet là bộ phát hiện được sử dụng. Tên mới bao quát nội dung hiện có hơn.
2. Gộp **2.3. Khoảng cách Euclid** vào một tiểu mục về **Xác định vùng mắt từ điểm mốc** trong phần 2.2. Hiện mục này chỉ có một công thức và ứng dụng hẹp, chưa cần đứng ngang cấp với các mảng lớn. Công thức dùng tính kích thước ROI từ khoảng cách hai mắt, không trực tiếp kết luận mắt nhắm/mở.

Nếu thực hiện việc gộp mục 2.3, cần cập nhật lại số mục tiếp theo và các tham chiếu khi biên tập toàn Chương 2. Đề xuất này chưa thực hiện thao tác đánh số lại.
