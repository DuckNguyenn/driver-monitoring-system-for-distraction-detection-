# Kết quả dọn thư mục dự án - 07/10/2026

Đã dọn khoảng **3.033 GiB**, gồm 57433 lượt xóa file trong 108 mục. Các lượt dọn sau kiểm thử bao gồm bytecode và executable được tạo lại; con số trên là tổng dung lượng tệp đã xóa.

Đã kiểm tra tham chiếu trong runtime, YAML/manifest, công cụ train/test, notebook và báo cáo trước khi xóa. Các mục dưới đây được xóa trực tiếp trong workspace.

| Đã dọn | Lý do |
|---|---|
| `test_yolo_face_detector/` | Prototype detector cũ; luồng chính dùng YuNet |
| `DA2/` | Schematic/PCB KiCad trống, không có linh kiện hoặc net |
| `camera_classical/.venv/` | Môi trường PC cũ lồng trong thư mục; giữ `.venv` ở gốc |
| `radxa_rock4d/python_runtime/models/` | Hai checkpoint trùng SHA256 với checkpoint gốc được giữ |
| `radxa_rock4d/config/` | `classes.txt` không có nơi đọc và ghi ngược lớp mắt; nhãn dùng manifest |
| `models/eye_refined_v2/`, `eye_refined_v3/` | Candidate không được chọn; giữ v1 vì bước train v4 đọc nó |
| `kaggle_output/yolov10/`, `runs/`, `onnx_exports/`, pretrained detector | Mã nguồn, trọng số và kết quả YOLOv10 detection không dùng trong hệ thống classifier |
| `.cache/uv-rknn/cache/` và archive bộ cài uv | Cache tải gói; executable uv, Python và môi trường SDK cài đặt được giữ |
| `dist/` và kết quả kiểm tra ZIP cũ | ZIP trước các bản sửa PC; tạo lại từ đúng manifest khi bàn giao |
| Ảnh/PDF render báo cáo cũ | Giữ bản Word/PDF hoàn thiện và QA hiện tại |
| `__pycache__/`, `firmware_test.exe` | File sinh ra khi chạy/kiểm thử, có thể tạo lại |

Giữ nguyên model hiện tại, model nền cần đối chiếu/chuyển đổi, dataset trong `kaggle_output/data/`, dữ liệu CEW/GENKI/SMILES, cache đặc trưng để tái huấn luyện, video người dùng, ESP32 firmware và môi trường PC/RKNN. Các DOCX đang mở trong Word và tài liệu gốc được giữ. Kiểm tra SHA256 cho các tệp được bảo vệ và đối chiếu số file/dung lượng dataset đều đạt trong từng lượt dọn.

Sau các thay đổi, **67 test runtime + 2 test wrapper PC đạt**, `pip check` đạt, mô phỏng firmware đạt; model mắt/ngáp/YuNet trong profile PC đều đúng checksum. Môi trường WSL vẫn nạp được Toolkit2 2.3.2 và Torch 2.4.0+cpu. Kiểm thử NPU và còi thật trên bo chưa được thực hiện.

Báo cáo hoàn thiện có 66 trang, 14 hình, 14 bảng đánh số và 20 biểu thức; đã kiểm tra PDF và xem bố cục/hình. Đã loại 21 đề mục ngoài phạm vi; các mục chưa có kết quả vẫn để trống.

- [Cấu trúc và vai trò thư mục](../REPOSITORY_STRUCTURE.md)
- [Chi tiết từng mục đã xóa, dung lượng và hash bảo vệ](project_cleanup.json)
- [Kết quả kiểm tra sau khi dọn](project_cleanup_checks.json)
- [Báo cáo Word](BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.docx)
- [Báo cáo PDF](BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.pdf)
