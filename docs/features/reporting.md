# Báo cáo và sơ đồ

## Tên và phạm vi phải giữ

Tên chính thức: **HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ**.
Tên file cũ có chữ buồn ngủ không cho phép tự thay tên đề tài trong nội dung.
Tài liệu mẫu dùng tham khảo văn phong; báo cáo mô tả đúng project, không thêm GPS hoặc giọng nói.
Theo yêu cầu mới: bỏ toàn bộ nội dung app mobile trong báo cáo; các đề mục đang trống giữ nguyên nội dung trống.
Các kết quả đã có vẫn giữ số liệu và giới hạn kiểm chứng, không bổ sung kết quả giả.

## Artifact đang giữ

- `BaocaoDA/Chuong2_test.docx` và `Chuong3_test.docx` có ảnh mặt cá nhân, chỉ có trên máy; các đường dẫn dạng code dưới đây là file cục bộ.
- [Word hiện hành](../../reports/BAO_CAO_GIAM_SAT_BUON_NGU_CHINH_SUA.docx).
- [PDF kiểm tra](../../reports/BAO_CAO_GIAM_SAT_BUON_NGU_CHINH_SUA.pdf).
- [Nguồn Markdown](../../reports/BAO_CAO_GIAM_SAT_BUON_NGU_CHINH_SUA.md).
- Bộ file `...HOAN_THIEN` là bản trước: Word đang giữ mở nên lượt mới lưu riêng, không ghi đè.
- Sơ đồ/ảnh nguồn dưới `report_assets/`; báo cáo xuất không phải tài liệu khởi động của agent.

## Khi chỉnh báo cáo

Đọc đúng chương/đề mục, kiểm tra code/model/manifest hoặc evidence có ngày tương ứng.
Mô tả kiến trúc YuNet, YOLOv8n classification, quyết định thời gian, serial và web đúng chức năng.
Hình kiến trúc tổng thể và thiết kế hệ thống phải khớp luồng dữ liệu thật.
Mọi chỉ tiêu F1/FPS/latency/2 giờ phải phân biệt mục tiêu, kết quả PC và kết quả trên Radxa.
Kết quả setup CPU và nhận camera có bằng chứng mới; nghiệm thu AI/NPU/serial trên bo vẫn chưa đủ.
Chương 2 chỉ trình bày khái niệm, nguyên lý, cấu trúc và công thức tổng quát. Lựa chọn thành phần, phân công xử lý, cấu hình và luật riêng của đề tài thuộc Chương 3; không đưa hướng dẫn lập trình vào cơ sở lý thuyết.

## Viết lại và bổ sung hình ngày 2026-10-24

- Áp dụng humanize: viết lại 126 đoạn, giữ giọng báo cáo kỹ thuật và số liệu đã có.
- Bỏ nội dung điện thoại trong lời văn, mục lục, tài liệu tham khảo và hai sơ đồ nhúng.
- Thêm năm hình về ROI/landmark, NMS, tích chập, ghép chớp hai mắt và xác nhận ngáp theo thời gian.
- Thay sơ đồ kiến trúc tổng thể và luồng web; giữ các lưu đồ xử lý, serial, trạng thái và triển khai NPU.
- Bản cuối có 23 hình, 19 bảng, 20 công thức, 38 tài liệu tham khảo; 11 đề mục trống được đối chiếu với bản gốc.
- Word COM cập nhật mục lục/PAGEREF và xuất PDF 77 trang. Đã xem toàn bộ trang bằng rasterizer documents + Poppler.
- Kiểm tra DOCX/PDF/Markdown không còn từ khóa mobile; loại cả hai ảnh nhúng cũ, bảng/công thức không đổi.
- Bản gốc và log ở `.cache/report-humanize/`; nguồn hình mới ở `report_assets/humanized/`.
- Bằng chứng: [report-humanize](../evidence/2026-10-24-report-humanize.json).
- Hồ sơ lượt trước: [report-review](../evidence/2026-10-15-report-review.json).

## Nguồn hình trực quan ngày 2026-10-24

- Đã xem báo cáo mẫu 82 trang, tập trung trang PDF 22, 30, 35, 37, 44–45, 59–60: ảnh thật, trước–sau, chú giải phần cứng và lưu đồ.
- [Thư viện xem trước](../../reports/THU_VIEN_HINH_THAM_KHAO.html) có 12 hình tải từ OpenCV, CS231n, conv_arithmetic, Radxa và Espressif.
- [Danh sách nguồn](../../reports/NGUON_HINH_THAM_KHAO.md) ghi vị trí đề xuất, chú thích, quyền sử dụng và giới hạn của từng hình.
- Ảnh gốc cùng URL, kích thước, SHA256 ở `report_assets/web_references_20261024/`; 8 hình ưu tiên, 4 dự phòng.
- Loại một hình mắt/ngáp vì nhãn nguồn MRL chưa khớp hình màu; không dùng ảnh này làm bằng chứng dữ liệu.
- Đã xem toàn bộ thư viện trên Edge, 12/12 ảnh tải được, không tràn ngang. Lượt tìm hình chưa thay đổi Word/PDF.
- Bằng chứng: [report-image-sources](../evidence/2026-10-24-report-image-sources.json).

## Chương 2 chỉnh lý ranh giới lý thuyết ngày 2026-10-25

- Bản 24/10 và đánh giá trước còn lẫn thiết kế: BGR theo thư viện, hai bộ phân loại, trọng số dùng chung, luật trạng thái và hợp nhất cảnh báo. Không tiếp tục dùng bản đó làm chuẩn cơ sở lý thuyết.
- [Bản chỉnh lý trước](../../BaocaoDA/CHUONG_2_CO_SO_LY_THUYET_CHINH_LY.docx): 12 trang, 7 mục lớn, 26 tiểu mục, 8 hình, 11 công thức native OMML, 27 nguồn tham khảo; bản hiện hành là Chuong2_test ở phần bàn giao dưới đây.
- [Bố cục đã chỉnh lý](../../BaocaoDA/DE_MUC_CHUONG_2_DA_THONG_NHAT.md) đổi tên phần thời gian và công cụ để phản ánh nội dung nguyên lý, không mô tả triển khai.
- [Ghi chú phân định chương](../../BaocaoDA/RANH_GIOI_CO_SO_LY_THUYET_VA_THIET_KE.md) ghi các nội dung cần dành cho Chương 3–5; chưa chèn vào những chương đó.
- RGB chỉ còn mô hình màu và biểu diễn ảnh. CNN, EMA, hysteresis, FSM và hình minh họa đều trình bày nguyên lý chung; không còn trạng thái, phân công hoặc luật riêng của DA2.
- Giữ trống thông số camera rời: 2.6.2 cũ → 2.5.2 mới. Không có nội dung mobile hoặc kết quả thực nghiệm tự bổ sung.
- Hai reviewer đã rà chéo lời văn theo ranh giới mới; nguồn chính thống đã kiểm tra. Word cập nhật field/xuất PDF, rasterizer documents tạo PNG; đã xem đủ 12 trang sau lần xuất cuối, gồm hình và công thức.
- Tài nguyên mới ở `report_assets/chapter2_theory_20261025/`, nháp/build/QA ở `.cache/chapter2-theory-20261025/`; [bằng chứng](../evidence/2026-10-25-chapter2-theory-boundary.json).
- Giữ bản Word cũ; chưa ghép vào báo cáo đầy đủ, không đổi code/model/ngưỡng. Hồ sơ lượt trước: [review 24/10](../evidence/2026-10-24-chapter2-review.json).

## Kiểm tra bàn giao

- Chương 2 hiện hành theo bản người dùng sửa: `BaocaoDA/Chuong2_test.docx`, đã cập nhật trực tiếp và mở lại trong Word ngày 25/10; giữ bản gốc ở `.cache/chapter2-test-flow/Chuong2_test.before.docx`.
- Tham khảo mạch báo cáo mẫu: điểm ảnh/biểu diễn → chuỗi công đoạn → tiền xử lý/nội suy → ROI/chất lượng → thuật toán khuôn mặt/CNN → thông tin thời gian. Giữ ranh giới cơ sở lý thuyết và thiết kế.
- Giữ cả 7 ảnh nhúng người dùng bổ sung, kiểm bằng SHA256; sửa biểu thức ROI và ký hiệu Laplace, thêm sơ đồ xử lý tổng quát. Hình IoU chưa xác định được nhà xuất bản gốc, không gán nguồn giả.
- Bản mới có 15 trang, 11 hình, 12 công thức (8 OMML + 4 ảnh giữ nguyên), 29 nguồn. Mục camera vẫn trống; không mobile, không ghép báo cáo đầy đủ.
- Word đã xuất bản làm việc; canonical rasterizer tạo PNG và đã xem đủ 15 trang. File đã lưu trùng SHA256 với bản được render; helper mở lại Word bị chờ sau khi mở file, đã dừng riêng helper, giữ các tài liệu Word khác.
- [Bằng chứng bản người dùng](../evidence/2026-10-25-chapter2-test-flow.json); nháp/build/QA ở `.cache/chapter2-test-flow/`, sơ đồ/nguồn ở `report_assets/chapter2_test_flow_20261025/`. Các bản NGAN_GON/CHINH_LY trước chỉ để đối chiếu.
- Người dùng yêu cầu dùng ảnh mặt từ video dataset: đã thay riêng Hình 2-2 bằng khung hình của video tự thu thập và kết quả lọc Gaussian thật; chú thích không còn gán nguồn ảnh cho OpenCV. Chỉ ảnh được chọn này được phép đưa vào báo cáo theo yêu cầu mới.
- [Bằng chứng thay hình khuôn mặt](../evidence/2026-10-25-chapter2-face-illustration.json): giữ 15 trang, 14 ảnh nhúng còn lại và toàn bộ lời văn ngoài một chú thích; kết quả Gaussian được tính lại trùng khớp. Đã xem trang 3–5; 12 trang còn lại trùng từng pixel với bản đã review. Backup/khung gốc ở `.cache/report-face-illustration/`, ảnh minh họa ở `report_assets/chapter2_user_face_20261025/`; video gốc không đổi.

- Review Chương 1 hiện hành: [bản ngắn gọn](../../BaocaoDA/CHUONG_1_TONG_QUAN_NGAN_GON.docx), 3 trang, đủ mục 1.1–1.7; rút từ 2259 xuống 924 từ theo yêu cầu.
- Có 3 chú thích cuối trang từ WHO, NHTSA và CDC/NIOSH; chỉ xuất Chương 1 trong `BaocaoDA/`, không ghép vào báo cáo đầy đủ.
- Đã xem đủ 3 trang qua Word PDF + rasterizer documents: [chapter1-short-review](../evidence/2026-10-24-chapter1-short-review.json). Giữ bản cũ 6 trang vì người dùng đang mở Word.

1. Giữ bản gốc trước thao tác có thể ghi đè; không chạy lại script sửa một lần khi chưa đọc điều kiện.
2. Kiểm tra heading, caption, ảnh/bảng, số liệu, đường dẫn và tên đề tài trong DOCX.
3. Render Word/PDF rồi xem toàn bộ trang và kiểm tra lại các trang sửa; XML/ZIP check không thay visual QA.
4. Ghi rõ renderer/môi trường và giới hạn nếu không render được.

Các báo cáo/ảnh lớn mở theo trang/phần, không dump vào context của task camera hoặc API.

## Chương 3 tính toán thiết kế ngày 2026-10-25

- `BaocaoDA/Chuong3_test.docx`: 14 trang, 8 mục lớn, 25 tiểu mục, 7 hình và 3 bảng; hai subagent đánh giá chéo và chọn bố cục B8.
- [Đề mục đã đánh giá](../../BaocaoDA/DE_MUC_CHUONG_3_DA_DANH_GIA.md); nguồn hình SVG/PNG ở `report_assets/chapter3_design_20261025/`.
- Người dùng chốt ESP32-WROOM-32, nền ảnh sản phẩm trắng và đường nối không chồng. Đã cho phép dùng công cụ khác draw.io; bản cuối đặt tuyến nối cố định và xuất PNG khoảng 2250 px.
- Dùng đúng ảnh mặt đã cho phép ở Chương 2, tạo ROI/đầu vào bằng code thật; ngáp dùng toàn mặt mở rộng, không Gaussian classifier. Tham số thiết kế theo profile near/medium.
- Đã xem đủ 14 trang cuối bằng Word PDF + canonical rasterizer, giữ nguyên Chương 2, không ghép báo cáo đầy đủ và không sửa runtime/model/firmware. [Bằng chứng](../evidence/2026-10-25-chapter3-design.json).


## Feedback sơ đồ Radxa ngày 2026-10-25

- Đã bỏ PC khỏi sơ đồ, ba đoạn mô tả và một ô bảng; chỉ giữ Radxa ROCK 4D / RK3576. Sơ đồ tổng quan có webcam USB, ESP32-WROOM-32 → ảnh buzzer, nhật ký JSONL/SQLite và web; các nhánh không chồng chữ.
- Đã cập nhật trực tiếp BaocaoDA/Chuong3_test.docx và mở lại trong Word, giữ 14 trang. Word Save As PDF + canonical rasterizer; đã xem đủ 14 trang, kiểm lại trang 2 sau sửa ô bảng. DOCX/PDF không còn PC; 6/6 hình khác và Chương 2 giữ nguyên. [Bằng chứng và SHA](../evidence/2026-10-25-chapter3-radxa-diagram.json).
- Backup và QA ở .cache/chapter3-radxa-review/; nguồn report_assets/chapter3_design_20261025/overview.svg và PNG đã cập nhật. Không chạy lại builder cũ; mọi sửa tiếp dùng bản Word hiện hành.
- Ảnh webcam là bản tham khảo cùng kiểu vỏ, không phải tệp đính kèm gốc; ảnh buzzer minh họa, chưa xác định mẫu lắp thực tế. Chương 2 và mục thông số camera giữ nguyên.


## Đề mục Chương 4 ngày 2026-10-25

- [Đề mục đề xuất](../../BaocaoDA/DE_MUC_CHUONG_4_DE_XUAT.md): 7 mục lớn, 23 tiểu mục về chuẩn bị, lắp ráp, dữ liệu/huấn luyện, phần mềm, web, triển khai Radxa và vận hành.
- Chưa chốt đề mục hoặc chèn nội dung Word. Giữ ranh giới Chương 3 thiết kế, Chương 4 thi công, Chương 5 kết quả; không đưa PC/mobile/Tailscale hoặc khẳng định NPU/cabin đã hoàn tất.
