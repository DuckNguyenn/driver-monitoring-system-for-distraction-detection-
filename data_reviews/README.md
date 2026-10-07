# Nhãn mắt trên vùng cắt runtime

`eye_roi_labels.json` chứa 215 khuôn mặt từ các ảnh GENKI đã có cục bộ và dataset ngáp của dự án. Từng mắt được xem trên ảnh gốc cùng vùng cắt YuNet rồi gán `Open`, `Closed` hoặc `Unknown`. Đây là nhãn do coding agent kiểm tra bằng ảnh, cần người làm đề tài rà soát khi chuẩn bị nghiệm thu.

`Open` yêu cầu thấy khe mắt/iris; `Closed` là mi mắt khép; ảnh mờ, kính che hoặc trạng thái không rõ được giữ `Unknown` và không dùng làm nhãn huấn luyện. Nhãn smile/yawn của nguồn không quyết định nhãn mắt.

`eye_roi_labels_v2.json` giữ nguyên nhãn, chuyển đúng ca lỗi đã biết `file0127.jpg` từ validation sang train để chữa lỗi bằng hard negative. Các ảnh validation/test khác giữ nguyên. Ca hồi quy này không phải dữ liệu đánh giá độc lập.

CEW cung cấp thêm ảnh nhắm mắt từ nguồn của tác giả, lưu ở `.cache/cew`, kiểm tra checksum và cắt bằng cùng YuNet. Các khuôn mặt trong cùng ảnh gốc được gán cùng split. Chỉ mục và vùng cắt đã dùng nằm trong `.cache/eye_refinement_v4/records.json`.

Các tập ảnh này chưa chứng minh việc tách theo người/clip. Ảnh CEW chỉ phục vụ nghiên cứu và không đưa vào gói bàn giao. [Trang nguồn CEW](https://parnec.nuaa.edu.cn/_upload/tpl/02/db/731/template731/pages/xtan/ClosedEyeDatabases.html); trích dẫn Song, Tan, Liu và Chen, *Eyes Closeness Detection from Still Images with Multi-scale Histograms of Principal Oriented Gradients*, Pattern Recognition 47 (2014), 2825–2838.
