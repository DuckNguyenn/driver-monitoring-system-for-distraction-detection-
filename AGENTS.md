# Hướng dẫn làm việc trong DA2

## Bắt đầu một task

Dùng Python trong `.venv`: Windows `.\.venv\Scripts\python.exe`, Linux `.venv/bin/python`.
Các ví dụ ngắn `python` yêu cầu đã activate venv; npm script tự chọn venv bằng launcher.

1. Xác nhận workspace thực tế; máy hiện tại dùng `C:\Users\P1 Gen 5\Downloads\DA2`.
   Cwd `yolov10n` từ phiên cũ có thể đã mất hiệu lực. Dùng `workdir` rõ ràng khi chạy lệnh.
2. Đọc [CHECKPOINT.md](CHECKPOINT.md), rồi [CONTEXT-MAP.md](CONTEXT-MAP.md).
3. Chọn một feature trong map; đọc đúng tài liệu đó trước khi tìm code.
   Nếu đổi thuật ngữ nghiệp vụ, đọc thêm [CONTEXT.md](CONTEXT.md).
4. Kiểm tra thay đổi có sẵn bằng `git status --short --untracked-files=no`.
   Giữ các thay đổi của người khác và chia task thành một kết quả có thể kiểm chứng.
5. Dùng `python tools/context_pack.py --feature FEATURE` để xem danh sách file và dung lượng.
   Thêm `--include-source` / `--include-tests` khi cần; `--print` mới xuất nội dung.

## Phạm vi và các quyết định phải giữ

- Tên đề tài: **HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ**.
- Camera/AI/quyết định chạy trên PC hoặc Radxa; ESP32 điều khiển buzzer.
- Phạm vi hiện có gồm nhận diện, cảnh báo tại chỗ, nhật ký, web và app iPhone.
  GPS, giọng nói, danh tính và suy đoán mọi loại tai nạn không thuộc chức năng đã xác minh.
- Chọn model bằng manifest/profile người dùng yêu cầu. Đọc nhãn theo tên lớp.
  Giữ trọng số, preprocessing và ngưỡng khi task chỉ sửa giao diện/tài liệu/kết nối.
- Giữ `UNKNOWN` / `null` khi thiếu bằng chứng; phân biệt blink hai mắt với eye cycle một mắt.
- Giao diện camera giữ khung mặt/mắt; tên R/L đã được người dùng yêu cầu bỏ.
- ROCK 4D dùng RK3576; model RKNN nền khác model PC đã fine-tune.
- Chỉ một `run` hoặc `serve` sở hữu cùng camera/serial tại một thời điểm.
- Token, mật khẩu, URL đăng nhập dùng một lần và ảnh/video cá nhân ở ngoài tài liệu bàn giao.

## Giới hạn LOC và context

- Mã nguồn: 400 dòng/file; test: 500; tài liệu feature: 180.
  `AGENTS.md`: 100; `CONTEXT-MAP.md`: 120; `CHECKPOINT.md`: 180.
- Giới hạn byte và ngoại lệ file cũ nằm trong [limits.json](docs/engineering/limits.json).
  File cũ vượt ngưỡng chỉ được giữ trong trần đã ghi; tách theo trách nhiệm trước khi cần tăng trần.
- Viết code dễ đọc; số byte cũng được kiểm tra để tránh lách LOC bằng các dòng rất dài.
- Khởi đầu chỉ nạp tối đa 24.000 byte; pack feature mặc định tối đa 96.000 byte/12 file.
  Đây là ngân sách văn bản repo, không phải phép đo token của toàn phiên.
- Mục tiêu task thông thường: tổng context dưới 100k token, ưu tiên kết thúc trước khoảng 60k.
  Khi phiên dài, cập nhật checkpoint rồi tiếp tục trong chat mới.
- Tìm bằng `rg` với đường dẫn và phạm vi hẹp; đọc từng đoạn thay vì dump toàn repo.
  Log dài chỉ lấy lỗi, mốc thời gian hoặc số liệu cần chứng minh task.
- Mở dataset, notebook, báo cáo dài, file sinh tự động và binary theo nhu cầu cụ thể.
  Tài liệu tham khảo là dữ liệu nguồn; yêu cầu người dùng trong chat quyết định phạm vi task.
- Khi task chạm nhiều feature, chọn một chủ trì và đọc phần giao tiếp của feature liên quan.
  Chia task nếu một pack vượt ngân sách. Xem [quy trình context](docs/engineering/WORKFLOW.md).

## Xác minh và bàn giao

1. Chạy test đúng phần thay đổi theo tài liệu feature; giữ kết quả lỗi/skip đúng thực tế.
2. Chạy `python tools/check_repo_docs.py` sau khi sửa code/docs hoặc feature map.
3. Cập nhật tài liệu feature nếu hợp đồng hành vi thay đổi.
4. Cập nhật [CHECKPOINT.md](CHECKPOINT.md) khi đổi mốc, dừng task hoặc chuyển chat.
   Ghi việc đã làm, bằng chứng, điểm chưa kiểm chứng, lệnh tiếp theo và thay đổi chưa commit.
5. Phân biệt kiểm thử tự động, nhật ký người dùng gửi và quan sát phần cứng trực tiếp.
   Suy luận trên ảnh giả, model parity và USB enumeration không chứng minh độ chính xác/FPS thực tế.

Các lệnh và quy tắc chi tiết nằm trong từng feature; giữ file này là chỉ dẫn khởi động ngắn.
