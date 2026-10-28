# Cấu trúc dự án sau khi dọn

> Tiếp tục theo feature: [bản đồ context](CONTEXT-MAP.md), [checkpoint mới nhất](CHECKPOINT.md), [docs](docs/README.md).

Runtime chính là `python -m driver_monitor`, dùng YuNet và hai classifier YOLOv8n. Profile camera hiện tại là `configs/camera_pc.yaml`, chọn manifest `models/yawn_camera_refined/manifest.json`. Phần cảnh báo gồm USB serial → ESP32 → buzzer.

| Thư mục/tệp | Vai trò và lý do giữ |
|---|---|
| `AGENTS.md`, `CONTEXT-MAP.md`, `CONTEXT.md`, `CHECKPOINT.md` | Hướng dẫn agent, điều hướng feature, glossary và bàn giao chat |
| `docs/` | Tài liệu feature, giới hạn LOC/byte, registry context và bằng chứng setup |
| `tools/context_pack.py`, `tools/check_repo_docs.py` | Chọn context có giới hạn và kiểm tra docs/LOC/link |
| `driver_monitor/` | Runtime dùng chung: camera/video, ROI, suy luận, logic thời gian, serial và nhật ký |
| `driver_monitor/dashboard_*.py` | Snapshot, API LAN riêng tiến trình, hàng đợi preview và chỉ mục lịch sử SQLite |
| `frontend/shared/`, `frontend/web/`, `frontend/mobile/` | Kiểu/API/kết nối chung, dashboard React + Vite, app iPhone React Native + Expo Go |
| `frontend/web/dist/` | Web đã build, Python phục vụ trực tiếp; Radxa không cần Node.js |
| `package.json`, `package-lock.json`, `requirements-dashboard*.txt`, `DASHBOARD.md` | Workspaces, dependency khóa và hướng dẫn vận hành web/app |
| `configs/` | Cấu hình PC, cấu hình chung và profile đối chiếu bản ngáp trước sửa |
| `models/yawn_camera_refined/` | Model ngáp hiện tại, manifest và kết quả đánh giá; manifest tham chiếu model mắt v4 |
| `models/eye_refined_v4/` | Checkpoint mắt PC hiện tại |
| `models/smile_refined/` | Model đối chiếu lỗi ngáp/cười, profile hồi quy mắt và nguồn khởi tạo bước sửa ngáp |
| `models/eye_refined/` | Lớp Linear khởi tạo cho `tools/refine_eye_tail.py`; chưa thể xóa khi cần tái huấn luyện |
| `models/manifest.json`, model ONNX/RKNN nền, YuNet | Model nền để đánh giá tương đương, chuyển đổi RKNN và đối chiếu; khác trọng số PC hiệu chỉnh hiện tại |
| `camera_classical/` | Hai checkpoint gốc được manifest/exporter tham chiếu; chương trình đối chiếu hình học PC cùng wrapper/test tương thích |
| `esp32_buzzer/` | Sketch còi, ACK, heartbeat/watchdog và sơ đồ nối dây |
| `radxa_rock4d/` | Wrapper runtime/conversion và dịch vụ systemd cho ROCK 4D; YAML cấu hình chung ở `configs/` |
| `scripts/` | Lệnh chạy camera/video và chuẩn bị môi trường Linux/RKNN |
| `tools/` | Công cụ thu video, fine-tune, kiểm thử, chuyển model, đóng gói và tạo báo cáo |
| `tests/` | Test runtime và ảnh hồi quy lỗi mắt/ngáp/cười đã biết |
| `train_eye_classifier.ipynb`, `train_yawn_classifier.ipynb` | Hai notebook phân loại đang phù hợp với kiến trúc model |
| `kaggle_output/data/` | Snapshot dataset cục bộ; evaluator và quy trình tạo dữ liệu huấn luyện còn sử dụng |
| `data_reviews/` | Nhãn mắt đã rà soát và lịch sử chuyển ca lỗi đã biết sang train |
| `data_collection/` | Quy trình thu/gán nhãn video, mẫu annotation cho nghiệm thu độc lập |
| `data_collection/yawn_distance/README.md`, `configs/yawn_distance_training.yaml` | Thu clip gần–trung bình–xa, native downsampling/blur và fine-tune Classify; video/nhãn cá nhân nằm tại máy |
| `models/blur_refined/`, `configs/blur_training.yaml`, `configs/camera_blur_candidate.yaml` | Checkpoint/ONNX thử, tham số fine-tune ảnh mờ và profile ngưỡng validation 16/5 |
| `.cache/blur_refinement/`, `reports/blur_refinement/` | Đặc trưng, ảnh review cục bộ, replay ba cấu hình và kết quả tổng hợp; ảnh/log giữ tại máy |
| `reports/` | Bộ báo cáo hoàn thiện Word/PDF/Markdown và báo cáo fine-tune ảnh mờ mới nhất; JSON, video và log phục vụ kiểm thử được giữ |
| `report_assets/` | Hình minh họa, sơ đồ và nguồn vector dùng để tạo báo cáo |
| `logs/` | Nhật ký camera thực; một số phiên là đầu vào phân tích lỗi, không phải toàn bộ đều là file tạm |
| `.venv/` | Môi trường PC đang dùng |
| `.venv-rknn/`, `.cache/python-rknn/` | Môi trường SDK Linux và Python mà môi trường này tham chiếu |
| `.cache/cew/`, `genki/`, `smiles/` | Dữ liệu bổ sung cho mắt nhắm và nụ cười; công cụ huấn luyện/đánh giá còn đọc |
| `.cache/eye_refinement*/`, `yawn_refinement/`, `yawn_camera_refinement/`, `debug/` | Đặc trưng, chỉ mục và script chuẩn bị dữ liệu để tái tạo model; không xóa cả `.cache` |
| `.codex/` | Cấu hình công cụ làm việc; tách khỏi runtime sản phẩm |
| `BAO_CAO_DA2_HE_THONG_GIAM_SAT_TAI_XE.docx` | Tài liệu gốc tham khảo, được kiểm tra giữ nguyên trong quy trình tạo báo cáo |

Đã dọn prototype `test_yolo_face_detector`, dự án KiCad trống `DA2`, môi trường PC cũ lồng trong `camera_classical`, checkpoint Radxa trùng lặp, artifact mắt v2/v3 không được chọn, cache tải gói SDK, ZIP đóng gói cũ và các ảnh/PDF render trung gian. Tệp `radxa_rock4d/config/classes.txt` không có nơi đọc và ghi ngược nhãn mắt đã được dọn; nhãn chính xác vẫn đọc từ manifest. Trong `kaggle_output`, đã dọn mã nguồn vendored, pretrained detector, ONNX và kết quả train/test YOLOv10 detection cũ; dataset trong `data/` được giữ nguyên. Tài liệu gốc tham khảo vẫn giữ nguyên.

`dist/` được tạo lại khi chạy `tools/build_radxa_bundle.py`. Công cụ hiện chọn manifest nền `models/manifest.json`; phải chọn/chuyển trọng số PC hiệu chỉnh trước khi bàn giao bản NPU tương ứng. Xem `DEPLOY_RADXA.md`.

Danh sách đã xóa, dung lượng và kiểm tra bảo toàn nằm trong `reports/project_cleanup.json`. Lệnh `tools/clean_unused_project.ps1` mặc định chỉ in danh sách; thêm `-Apply` mới xóa các mục đã xác định. Không dùng công cụ này để xóa dữ liệu/model khác. Python có thể tạo lại `__pycache__` khi chạy.

Báo cáo hiện tại: `reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.docx`, `.pdf` và nguồn `.md` cùng tên. Báo cáo cập nhật fine-tune ảnh mờ ở `reports/BLUR_REFINEMENT.md`, kèm kết quả trong `reports/blur_refinement/`. Hồ sơ kiểm tra bản hoàn thiện ở `reports/reference_style/system_design_scope/`; các mục chưa đo phần cứng được giữ trống.

Các bản Word trung gian, báo cáo kiến trúc riêng và các báo cáo chẩn đoán/sửa lỗi cũ đã được dọn. Sơ đồ dùng trong báo cáo hiện tại, model, video và kết quả kiểm thử được giữ. Công cụ tạo Word/PDF mặc định dùng tên `HOAN_THIEN`; gói Radxa dùng PDF hiện tại. Nhật ký dọn báo cáo nằm trong `.cache/report_cleanup/audit.json`.
