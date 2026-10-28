# Checkpoint bàn giao — 2026-10-28, Asia/Bangkok

## Mục tiêu hiện tại và cách bắt đầu

- Workspace: `C:\Users\P1 Gen 5\Downloads\DA2`; PowerShell; Python `.\.venv\Scripts\python.exe`.
- Nhánh: `feature/lan-dashboard-ios`; HEAD trước lần xuất bản 28/10: `a0fbdda`.
- Đã tạo [hướng dẫn chạy](HUONG_DAN_CHAY_CHUONG_TRINH.md), tìm firmware ESP-IDF; không mở camera/serial hoặc flash.
- Chương 3 đã QA 14 trang; Chương 4 mới đề xuất đề mục, chưa viết Word.
- Đọc [AGENTS.md](AGENTS.md) → checkpoint này → [CONTEXT-MAP.md](CONTEXT-MAP.md) → [runtime](docs/features/runtime.md) cho lệnh chạy; [reporting](docs/features/reporting.md) cho báo cáo.
- Chỉ nạp feature liên quan, chạy context pack; giữ context dưới 100k, ưu tiên dưới 60k.
- Không reset/clean hoặc hoàn nguyên công việc cũ; kiểm tra Git trước khi sửa.

## Xuất bản GitHub ngày 28/10

- Người dùng yêu cầu commit/push, chỉ loại file có tên chứa `prompt` (không phân biệt hoa/thường).
- Theo yêu cầu: báo cáo có ảnh mặt giữ ở máy, cùng dataset/cache/thông tin đăng nhập.
- Bản stage: 214 test Python (188 đạt, 26 skip dữ liệu/model cục bộ); 10 test client, 3 test web, TypeScript/build PASS. Không kiểm tra phần cứng.
- Đã sửa fixture phụ thuộc cache riêng, kiểm tra guard trên cây stage và danh sách loại trừ. [Bằng chứng](docs/evidence/2026-10-28-github-publish.json). Nhánh xuất bản `feature/lan-dashboard-ios`; xem `git log -1` và `git status -sb` để kiểm tra mốc/upstream.

## Chốt công cụ ESP32 và hướng dẫn chạy ngày 28/10

- Người dùng xác nhận nạp bằng **ESP-IDF**, không dùng Arduino IDE; giữ quyết định này khi viết Chương 4 và hướng dẫn vận hành.
- Đã rà DA2 (cả file ẩn/ignore), user projects, C:\Espressif và C:\esp: có SDK 5.5.4/v6.0.1, chưa thấy project IDF cho còi DA2. `.ino` chỉ là tham khảo; SDK và project khác không phải firmware DA2.
- Các cách PC/video/headless/web/app/Radxa và nhánh có điều kiện nằm trong hướng dẫn. Lệnh chính giữ profile near/medium; launcher cũ có thể chọn model khác.
- Đã kiểm checksum/model, web/APK/ZIP và parse 10 ví dụ CLI bằng stub không I/O. Firmware IDF/NPU chưa xác minh; đóng IDF Monitor trước khi host mở COM.

## Quyết định viết báo cáo phải giữ

- Tên đề tài: **HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ**.
- Văn phong tự nhiên, ngắn gọn, giọng báo cáo kỹ thuật; dùng skill humanize và documents khi sửa Word.
- Không đưa app mobile vào báo cáo, dù project có app. Không thêm GPS, giọng nói, danh tính hoặc kết quả chưa đo.
- Đề mục đang trống phải giữ trống. Trong bản Chương 2 hiện hành, `2.5.2 Thông số kỹ thuật camera rời` vẫn trống.
- Chương 2 trình bày khái niệm, nguyên lý, cấu trúc, công thức. Lựa chọn thành phần, cấu hình, phân công và luật riêng thuộc Chương 3; thi công ở Chương 4; kết quả ở Chương 5.
- Người dùng đã phản đối đoạn BGR/OpenCV/đầu vào classifier trong cơ sở lý thuyết. Không đưa hướng dẫn lập trình hoặc quy trình triển khai trở lại chương này.
- Dẫn dắt thành chuỗi: điểm ảnh và biểu diễn ảnh → các công đoạn xử lý ảnh → tiền xử lý/nội suy → ROI/chất lượng → khuôn mặt/điểm mốc → CNN/phân loại → thông tin theo thời gian.
- Phân biệt phân đoạn, phân loại và phát hiện. Nội suy là ước lượng giá trị điểm ảnh, không đồng nhất với diễn giải ngữ nghĩa.
- Báo cáo mẫu chỉ để tham khảo cách dẫn dắt, bố cục và hình. Không sao chép thuật toán khác hoặc các lỗi kiến thức của mẫu.
- Giữ lý thuyết, hình và chỉnh sửa thủ công của người dùng trong bản hiện hành; sửa trực tiếp file đó, có backup trước khi sửa.

## File hiện hành và trạng thái đã kiểm tra

| Artifact | Trạng thái |
| --- | --- |
| `BaocaoDA/Chuong2_test.docx` | Dùng bản này làm gốc cho mọi sửa tiếp; đã cập nhật trực tiếp |
| [Chương 1 ngắn gọn](BaocaoDA/CHUONG_1_TONG_QUAN_NGAN_GON.docx) | 3 trang, đủ 1.1–1.7, 3 chú thích nguồn; đã review |
| [Đề mục Chương 2](BaocaoDA/DE_MUC_CHUONG_2_DA_THONG_NHAT.md) | Bố cục theo bản người dùng, gồm chuỗi công đoạn xử lý ảnh |
| [Ranh giới lý thuyết và thiết kế](BaocaoDA/RANH_GIOI_CO_SO_LY_THUYET_VA_THIET_KE.md) | Ghi nội dung dành cho Chương 3–5; chưa chèn vào các chương đó |
| [Báo cáo đầy đủ](reports/BAO_CAO_GIAM_SAT_BUON_NGU_CHINH_SUA.docx) | Bản 77 trang kèm PDF/Markdown; chưa ghép Chương 1–2 review mới |

- Chương 2 có 15 trang, 7 mục lớn, 27 tiểu mục và 6 mục con về công đoạn; 11 hình, 12 công thức (8 OMML + 4 ảnh công thức), 29 nguồn tham khảo.
- File giữ cả 7 ảnh nhúng từ bản người dùng gửi. Công thức trích ROI và ký hiệu Laplace đã sửa; không đổi code/model/ngưỡng.
- Các bản `CHUONG_2_CO_SO_LY_THUYET_NGAN_GON.docx` và `...CHINH_LY.docx` trong `BaocaoDA/` chỉ để đối chiếu, không phải bản hiện hành.
- Nguồn mẫu DOCX: `C:\Users\P1 Gen 5\Downloads\ung-dung-xu-ly-anh-iot-trong-giam-sat-tai-xe-tren-o-to.docx`; đã đọc phần xử lý ảnh, không cần nạp toàn bộ báo cáo mẫu.
- Nháp/build/QA lần tổ chức lại: `.cache/chapter2-test-flow/`; bằng chứng [chapter2-test-flow](docs/evidence/2026-10-25-chapter2-test-flow.json).
- Không chạy lại các builder cũ để sửa một mục: chúng chưa phản ánh toàn bộ chỉnh sửa trực tiếp, đặc biệt ảnh mặt mới, và có thể đưa logo OpenCV trở lại.

## Chương 3 đã tạo ngày 25/10/2026

- Feedback mới đã hoàn tất: bỏ PC khỏi sơ đồ, ba đoạn thiết kế và một ô bảng; chỉ giữ Radxa ROCK 4D / RK3576. Bỏ nhãn “Phương án bo”; webcam USB và ESP32-WROOM-32 → ảnh còi buzzer; các nhánh không chồng chữ.
- Đã cập nhật trực tiếp `BaocaoDA/Chuong3_test.docx`, mở lại bản ghi được trong Word. Bản cuối 14 trang; giữ nguyên 6/6 ảnh khác và Chương 2. Backup trước thay ở .cache/chapter3-radxa-review/Chuong3_test.before-radxa-final.docx.
- Word Save As PDF + canonical documents renderer; đã xem đủ 14 trang, kiểm lại trang 2 sau khi sửa ô bảng. [Bằng chứng và SHA bản cuối](docs/evidence/2026-10-25-chapter3-radxa-diagram.json); PDF/PNG QA ở .cache/chapter3-radxa-review/. Chỉ sửa tiếp bản hiện hành, không chạy builder cũ.
- Webcam mới là ảnh tham khảo cùng kiểu vỏ, góc trước, không phải chính tệp người dùng đính kèm; buzzer là ảnh minh họa linh kiện. Không tự bổ sung thông số kỹ thuật camera hoặc kết quả phần cứng.

- Bản hiện hành: `BaocaoDA/Chuong3_test.docx`, 14 trang, 8 mục lớn, 25 tiểu mục, 7 hình và 3 bảng; chưa ghép báo cáo đầy đủ.
- Hai subagent đề xuất/đánh giá chéo, chọn bố cục B8 tách nhận diện → sự kiện → quyết định. [Đề mục và đánh giá](BaocaoDA/DE_MUC_CHUONG_3_DA_DANH_GIA.md).
- Chốt ESP32-WROOM-32 theo người dùng, ảnh bo tham khảo Espressif đúng module; sản phẩm nền trắng. Đệm đen letterbox giữ như dữ liệu kỹ thuật.
- Người dùng đã cho phép công cụ khác draw.io, yêu cầu cao nhất là hình trực quan và mũi tên không chồng. Bản cuối dùng SVG với tuyến nối cố định và PNG độ phân giải cao (hình tổng quan mới 3920 × 2760); nguồn ở `report_assets/chapter3_design_20261025/`.
- Tái dùng đúng khung mặt đã được cho phép ở Chương 2; minh họa được tính qua Vision/prepare_rgb. Ngáp dùng mặt mở rộng, ảnh xám chỉ đo chất lượng, không đưa Gaussian vào classifier.
- Thông số theo profile near/medium; không đồng nhất cấu hình camera_pc mặc định. Phân biệt UNKNOWN, blink/cycle, ACK và xác nhận âm thanh thật. Không bổ sung kết quả phần cứng chưa đo.
- Word Save As PDF + canonical documents rasterizer; đã xem đủ 14 trang cuối. Chương 2 giữ nguyên SHA256. [Bằng chứng](docs/evidence/2026-10-25-chapter3-design.json).

## Đề mục Chương 4 ngày 25/10/2026

- [Đề mục đề xuất](BaocaoDA/DE_MUC_CHUONG_4_DE_XUAT.md): Thi công và triển khai hệ thống, 7 mục lớn và 23 tiểu mục; nối tiếp bản Chương 3 chỉ dùng Radxa.
- Trình tự: chuẩn bị → lắp ráp → dữ liệu/huấn luyện → phần mềm giám sát/cảnh báo → web → triển khai Radxa → vận hành. Độ chính xác/FPS/độ trễ thuộc Chương 5; bước chưa làm giữ trống.
- Chưa chèn nội dung hoặc sửa Word; đề mục chưa được người dùng chốt. Giữ Chương 2–3 và các hình đã chỉnh.

## Hình 2-2 mới nhất

- Đã thay logo OpenCV bằng cặp ảnh khuôn mặt trích từ video tự thu thập và kết quả làm mờ Gaussian thật, theo yêu cầu trực tiếp của người dùng.
- Chú thích: “Hình 2-2. Ảnh khuôn mặt trước và sau làm mờ Gaussian. Nguồn: video tự thu thập.”
- Ảnh dùng trong Word: `report_assets/chapter2_user_face_20261025/figure_2_2_face_gaussian.jpg`.
- Nguồn/khung hình/tham số cụ thể ở [chapter2-face-illustration](docs/evidence/2026-10-25-chapter2-face-illustration.json). Không nhúng thêm ảnh/video cá nhân khác vào bàn giao.
- Ảnh trái/phải dùng cùng một crop; phải được tính bằng OpenCV GaussianBlur, kernel 73×73, sigma 12. Đây là tham số minh họa, không phải cấu hình runtime.
- Chỉ một hình và một chú thích thay đổi; toàn bộ lời văn khác và 14 ảnh nhúng còn lại được giữ. Video/dataset gốc không sửa.
- Backup trước sửa ảnh: `.cache/report-face-illustration/Chuong2_test.before-face.docx`; khung gốc/crop/QA ở cùng thư mục cache.
- Word xuất bản sao sang PDF, canonical documents renderer tạo PNG: đã xem trang 3–5; 12 trang còn lại trùng từng pixel với bản đã review đầy đủ.
- SHA256 `Chuong2_test.docx` khớp bằng chứng thay ảnh; bản QA 15 trang.

## Phân biệt thuật toán và những điểm còn cần review

- Runtime chính dùng YuNet tìm mặt và 5 điểm mốc, rồi hai YOLOv8n classification cho mắt/ngáp. Không mô tả YuNet như bộ đưa ra kết luận mất tập trung cuối cùng.
- Đã xác minh code ngày 25/10: [Vision](driver_monitor/vision.py) gọi FaceDetectorYN; Haar cascade chỉ nằm ở bản đối chiếu cũ [camera_classical](camera_classical/camera_classical.py).
- Không đưa Haar-like/AdaBoost vào báo cáo như thuật toán đang vận hành của hệ thống hiện tại.
- Hình ROI 2-3 là ví dụ RoI pooling của Fast R-CNN để giải thích lý thuyết, không phải kiến trúc DA2 đang dùng.
- Hình IoU con bướm được giữ từ bản người dùng; chưa xác định nhà xuất bản gốc. Không gán nguồn giả; nếu hoàn thiện xuất bản cần bổ sung nguồn hoặc thay hình phù hợp.
- Chưa ghép bản review vào báo cáo đầy đủ; chưa sửa Chương 3–5 theo cấu trúc review. Chỉ làm khi người dùng yêu cầu.
- Word có thể đang mở file: lưu/backup và bảo toàn chỉnh sửa mới trước thao tác. Không Quit toàn bộ Word hoặc đóng các tài liệu khác.
- Sửa ảnh bằng Word COM phải bảo đảm thay ảnh cũ, không chèn thêm: Chương 2 có 15 inline images, trong đó 4 là công thức dạng ảnh. Không giả định Undo một lần luôn phục hồi toàn bộ thao tác nhóm.
- PowerShell 5: đọc tiếng Việt bằng `Get-Content -Encoding UTF8`.

## Việc khác đang hoãn hoặc chỉ có bằng chứng lịch sử

- Tailscale Radxa/iPhone đã được người dùng yêu cầu để sau; không tự tiếp tục. Các IP, SSH, process, camera phải kiểm tra lại khi có yêu cầu phần cứng/kết nối.
- Radxa ROCK 4D dùng RK3576; log người dùng gửi trước có ONNX smoke và camera USB enumeration, chưa chứng minh FPS/độ chính xác, NPU hoặc còi ESP32 thực tế. Xem [radxa](docs/features/radxa.md).
- Profile người dùng chọn: `models/yawn_kaggle_near_medium/runtime.yaml`; cấu hình mặc định serve PC là `configs/camera_pc.yaml`, không tự hoán đổi.
- Bộ bo trước đó: `dist/DA2-radxa-onnx.zip`, `/home/radxa/DA2`; model RKNN nền cũ không đại diện cho model PC đã fine-tune hiện chọn.
- Android/iPhone dùng chung Expo app; UI 1.1.0 và APK `dist/android/DriverMonitor.apk` đã có bằng chứng thử tổng hợp trên LDPlayer 9 ngày 15/10. Chưa nghiệm thu điện thoại Android thật hoặc Radxa LAN trong lượt báo cáo. Xem [mobile-ui](docs/features/mobile-ui.md), [android](docs/features/android.md).
- Cảnh báo iPhone hiện có trong foreground; push nền/khóa màn hình và PWA/Web Push mới là hướng đề xuất. Xem [remote-access](docs/features/remote-access.md).
- Auto-glasses mặc định tắt; còn thiếu bằng chứng RGB kính/nhãn được review và nghiệm thu phần cứng. Không bật trên bộ ZIP bo đang dùng. Xem [glasses](docs/features/glasses.md).
- MCP context7/filesystem/playwright đã cài và kiểm tra ngày 20/10; cấu hình global và skill humanize không thuộc code runtime. Xem [codex-mcp](docs/evidence/2026-10-20-codex-mcp.json).

## Lệnh tiếp tục và kiểm tra

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/context_pack.py --feature reporting
git status --short --untracked-files=no
.\.venv\Scripts\python.exe -X utf8 tools/check_repo_docs.py
```

- Lượt xuất bản sửa ignore, liên kết file cục bộ và fixture test; giữ nguyên báo cáo/model/firmware, không mở camera/serial.
- Kiểm tra bàn giao 25/10: guard PASS; 16 test docs/context PASS ngoài sandbox. Lần đầu bị sandbox chặn thư mục tạm; chạy lại đạt. [Bằng chứng checkpoint](docs/evidence/2026-10-25-reporting-handoff.json).
- Sau sửa Word: render bằng documents, xem các trang thay đổi và kiểm các trang còn lại; XML/ZIP check không thay thế visual QA.
- Cần sửa công cụ context/docs: chạy thêm `.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_context_docs -v` theo workflow.
- Khi có yêu cầu chạy, chọn lệnh trong hướng dẫn và kiểm camera/COM/IP hiện tại. Source firmware IDF còn cần xác định; báo cáo chờ feedback tiếp theo, không tự ghép chương hoặc khôi phục Tailscale.

## Prompt dán vào chat mới

```text
Workspace: C:\Users\P1 Gen 5\Downloads\DA2.
Đọc AGENTS.md, CHECKPOINT.md, CONTEXT-MAP.md rồi đúng feature; giữ context dưới 100k.
Lệnh chạy ở HUONG_DAN_CHAY_CHUONG_TRINH.md; ESP32 dùng ESP-IDF, chưa tìm thấy source firmware DA2.
Báo cáo hiện hành cục bộ: BaocaoDA/Chuong2_test.docx và Chuong3_test.docx; giữ chỉnh sửa/hình người dùng, không ghép chương, không mobile, mục trống giữ trống.
Tailscale vẫn hoãn. Kiểm tra Git trước khi sửa; không hoàn nguyên công việc cũ.
```
