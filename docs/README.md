# Tài liệu DA2 theo feature

Tên đề tài: **HỆ THỐNG GIÁM SÁT VÀ PHÁT HIỆN SỰ MẤT TẬP TRUNG CỦA TÀI XẾ**.

## Điểm vào

1. [Checkpoint mới nhất](../CHECKPOINT.md): trạng thái và việc tiếp theo giữa các chat.
2. [Bản đồ feature](../CONTEXT-MAP.md): chọn một nhánh công việc trước khi đọc code.
3. [Thuật ngữ](../CONTEXT.md): dùng khi thay đổi ý nghĩa observation, blink, yawn hoặc trạng thái.
4. [Quy trình context/LOC](engineering/WORKFLOW.md): cách giữ task nhỏ và bàn giao.

## Quy ước đọc và cập nhật

- `features/`: hợp đồng hành vi, ranh giới thay đổi, bằng chứng và kiểm tra cho từng feature.
- `feature-map.json`: registry dùng cho `tools/context_pack.py`; chứa nguồn/test chính của mỗi nhánh.
- `engineering/limits.json`: giới hạn LOC/byte và trần ngoại lệ file cũ.
- `evidence/`: ghi nhận mốc phần cứng từ terminal người dùng; không chứa token hoặc ảnh cá nhân.
- `templates/`: khung task/checkpoint khi chia việc hoặc chuyển chat.
- `CHECKPOINT.md` ở root là checkpoint đang hoạt động duy nhất. Tạo bản lưu khi đổi mốc lớn,
  không duy trì hai file “latest” có cùng nội dung.

Các README/runbook có từ trước vẫn là tài liệu thao tác chi tiết, chỉ mở theo link của feature.
Một số đoạn lịch sử có kết quả kiểm thử cũ; dùng checkpoint và hồ sơ có ngày để hiểu trạng thái mới.

## Công cụ

```powershell
& '.\.venv\Scripts\python.exe' tools/context_pack.py --list
& '.\.venv\Scripts\python.exe' tools/context_pack.py --feature remote-access
& '.\.venv\Scripts\python.exe' tools/check_repo_docs.py
```

Lệnh đầu liệt kê feature; lệnh thứ hai chỉ liệt kê file/dung lượng, không dump mã nguồn.
Thêm `--include-source --include-tests` để chọn nguồn/test, thêm `--print` để xuất nội dung.
Tool chỉ đo văn bản repo, không đếm token system prompt, MCP, lịch sử chat hoặc reasoning.

Các npm script tương đương: `npm.cmd run check:docs` và `npm.cmd run context -- --feature remote-access`.
Launcher tự chọn Python trong `.venv` trên Windows/Linux; không cần cài thư viện bổ sung cho các tool này.
