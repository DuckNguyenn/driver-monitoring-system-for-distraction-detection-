# Quy trình task, LOC và context

## Mục tiêu

Đa số task thường ngày hoàn thành dưới 100k token tổng context; nên kết thúc hoặc bàn giao trước
khoảng 60k. Giới hạn repo hỗ trợ mục tiêu này bằng việc chọn ít tài liệu/code, không phải bảo đảm
số token của mọi model, system prompt, MCP hoặc lịch sử đã được nạp.

## Thứ tự đọc

1. `AGENTS.md` → `CHECKPOINT.md` → `CONTEXT-MAP.md`: tối đa 24.000 UTF-8 byte theo guard.
2. Chọn một feature; đọc tài liệu feature đó, chỉ mở runbook dài khi cần một thao tác cụ thể.
3. Đọc entrypoint và test sát lỗi; tìm symbol bằng `rg -n` với đường dẫn cụ thể.
4. Kiểm tra hợp đồng giữa hai feature khi task đi qua ranh giới; chia thành các lát nhỏ có test.

Không dùng bản chép toàn bộ chat cũ làm context đầu vào. Checkpoint giữ dữ kiện đã chọn và đường
dẫn bằng chứng; log/video/dataset được tra đúng thời điểm cần.

## Ngân sách thao tác

| Khoản | Quy tắc |
|---|---|
| Pack mặc định | Tối đa 96.000 UTF-8 byte, 12 file, gồm header file |
| Pack mở rộng | Tối đa 160.000 byte; ghi lý do trong task và chia tiếp nếu còn lớn |
| Văn bản đầu phiên | Tối đa 24.000 byte |
| Tool output | Ưu tiên từng đoạn hoặc kết quả JSON rút gọn; khoảng 4k token/lượt đọc là mục tiêu |
| Điều tra rộng | Lập bản đồ đường dẫn trước, đọc nội dung sau; không tải toàn bộ mọi feature |
| Khi chat dài | Chốt checkpoint trước khi compaction hoặc mở chat mới |

Byte không được gắn nhãn thành token. Tool trả `token_count: null` để tránh báo số đo giả.
Theo dõi token thực bằng chỉ báo của công cụ chat nếu có; system/MCP có thể tiêu tốn context nền.

```powershell
& '.\.venv\Scripts\python.exe' tools/context_pack.py --feature remote-access
& '.\.venv\Scripts\python.exe' tools/context_pack.py --feature monitoring --include-source --include-tests
& '.\.venv\Scripts\python.exe' tools/context_pack.py --feature monitoring --include-source --print
```

`--print` chỉ chạy sau khi file/byte budget đạt. Vượt ngưỡng sẽ dừng với lỗi, không tự cắt mất phần
cuối file. Muốn xem ít hơn, dùng danh sách file trả về và đọc symbol/đoạn cần thiết.
Model binary, khóa, `.env`, JSONL và thư mục dữ liệu cá nhân bị loại khỏi pack.

## Giới hạn file

Nguồn cấu hình duy nhất: [limits.json](limits.json).

| Loại | Trần dòng |
|---|---:|
| Production code và công cụ | 400 |
| Test | 500 |
| Tài liệu dưới docs/ | 180 |
| AGENTS.md | 100 |
| CONTEXT-MAP.md / CONTEXT.md | 120 |
| CHECKPOINT.md | 180 |
| Runbook cũ ngoài docs/ | 300 |

Dòng được tính từ `bytes.splitlines()`, có tính dòng trắng/comment; không suy diễn “logical LOC”.
Trần byte bổ sung bắt các file ít dòng nhưng quá dài. Viết code theo các bước dễ đọc, không gộp
nhiều statement chỉ để đạt LOC. Tách module theo trách nhiệm và interface có thể test.

### File lớn có sẵn

- `legacy_exceptions` ghi tên file, trần dòng/byte tại lúc áp dụng và lý do.
- Chỉ cho phép trần cố định của file đó; file mới/đổi tên không kế thừa ngoại lệ.
- Không tăng trần để làm guard xanh. Khi chạm trần, tách phần có interface rõ hoặc giảm độ dài.
- Sau khi tách, hạ/xóa ngoại lệ tương ứng. Thay ngưỡng phải có yêu cầu hoặc lý do rõ trong task.
- File sinh tự động, môi trường, dataset, model và báo cáo xuất được loại khỏi phép đếm nguồn.
  `frontend/mobile/android` là output Expo prebuild; config/plugin ngoài thư mục đó vẫn kiểm LOC/byte.

## Checklist kết thúc task

1. Test sát thay đổi đạt; nêu rõ lỗi/skip, môi trường và điều kiện đo.
2. `python tools/check_repo_docs.py` đạt: LOC/byte, link nội bộ, startup và tất cả feature pack.
3. Cập nhật tài liệu feature khi hành vi/interface thay đổi.
4. Cập nhật `CHECKPOINT.md` nếu có thay đổi trạng thái, bằng chứng hoặc việc tiếp theo.
5. Ghi phạm vi file đã sửa; giữ các thay đổi có sẵn trong worktree.

Task sửa tài liệu/công cụ context chạy `python -m unittest tests.test_context_docs -v`.
Các task khác dùng test trong feature-map hoặc tài liệu tương ứng; không gọi toàn bộ GPU/benchmark
chỉ vì sửa một liên kết. Full suite chạy khi có tác động chung hoặc trước nghiệm thu/release.

## Chuyển sang chat mới

Hoàn thiện [template checkpoint](../templates/CHECKPOINT.md), rồi dán prompt ở cuối checkpoint
đang hoạt động. Chat mới xác minh lại IP, process, camera, trạng thái job và worktree trước khi dùng
các giá trị có thể thay đổi. Kết quả lịch sử không tự trở thành kết quả kiểm thử mới.

Checkpoint phải đủ để tiếp tục khi không còn lịch sử chat: mục tiêu, quyết định đã chốt, bằng
chứng, việc chưa xong, lệnh tiếp theo, giới hạn môi trường và phần cần người dùng thao tác.
