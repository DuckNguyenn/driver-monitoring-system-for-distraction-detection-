# Kiểm tra bỏ sót ngáp trên camera ngày 07/10/2026

Trạng thái cập nhật: đã nhận video camera `20261007T070644_475102Z.avi`, hiệu chỉnh đầu classifier ngáp và xác nhận 2/2 sự kiện khi phát lại; đoạn cười không tạo sự kiện ngáp. Giữ nguyên ngưỡng và kiểm tra chất lượng ảnh. Xem [báo cáo sửa và giới hạn](YAWN_CAMERA_FIX.md). Đây là kiểm thử phát triển một người, chưa phải nghiệm thu độc lập.

Phần dưới lưu chẩn đoán ban đầu trước khi có video; các kết quả phát lại xác suất của log cũ vẫn dùng model/xác suất trước sửa.

Nguồn: `logs/20261007T064117_607240Z.csv` và JSONL cùng phiên. SHA256 CSV: `94054f0afe4b37dbece97f5649b75ce7f41736caa8ae0c864c0988965d0a71c5`.

Khung hình khớp ảnh người dùng có elapsed 114,594 s, frame 3411: quality=usable, eye_quality=usable, P(yawn) thô=0,80858, sau EMA=0,57885, yawn_state=no_yawn, yawn_count=0. Ngưỡng xác nhận là 0,70 liên tục 1 s.

Đoạn 112–116 s có 120/120 frame đạt quality=usable. Xác suất thô dao động từ 0,000000832 đến 0,94998. Chuỗi ứng viên dài nhất trong đoạn chỉ đạt 0,094 s. Trên toàn phiên, chuỗi dài nhất đạt 0,953 s; đó không phải thời lượng ngáp thật vì chưa có gán nhãn video.

Ba khả năng được kiểm tra:

1. EMA làm chậm tín hiệu: phát lại với EMA=0 vẫn không xác nhận được sự kiện.
2. Chất lượng toàn frame làm ngắt sự kiện: bỏ điều kiện này trong phép phát lại vẫn không có sự kiện; đoạn ảnh báo lỗi vốn có đủ chất lượng.
3. Điều kiện chuyển động mắt làm mất ngáp: bỏ điều kiện eye_motion trong phép phát lại vẫn không có sự kiện. Mã nguồn giữ kênh ngáp hợp lệ khi kênh mắt chuyển head_motion.

Kết quả thu hẹp vấn đề về đầu ra classifier/vùng ảnh đầu vào. Chưa phân biệt được nguyên nhân cụ thể do crop, model, tư thế hoặc ánh sáng vì CSV không giữ điểm ảnh. Không thể khôi phục hình ảnh từ xác suất.

Phép tái hiện có thể chạy:

```powershell
& '.\.venv\Scripts\python.exe' tools/analyze_yawn_trace.py --csv logs/20261007T064117_607240Z.csv --start 112 --end 116 --expect-yawn
```

Hiện lệnh trả mã lỗi 1 và `FAIL: reported yawn interval has no confirmed event.` Đây là lỗi đang được theo dõi, không phải một kiểm thử đã đạt. `reports/yawn_trace_diagnosis.json` lưu kết quả so sánh. Phép phát lại xác suất không thay thế suy luận từ ảnh; CSV cũng không chứa đầy đủ track_changed và tuổi frame khi chạy trực tiếp.

Thu video để kiểm tra:

```powershell
& '.\.venv\Scripts\python.exe' tools/record_yawn_check.py --source 0
```

Đóng cửa sổ Driver monitor trước để giải phóng camera. Công cụ đếm ngược 5 s rồi ghi 38 s theo hướng dẫn hiển thị: bình thường, ngáp, bình thường, cười, bình thường, ngáp, bình thường. Giữ camera ổn định và khuôn mặt đủ sáng. Video gốc, timestamp và mẫu annotation được lưu trong `reports/yawn_camera_check/`. Các giai đoạn hướng dẫn chưa phải nhãn đã kiểm chứng; cần xem video để xác định sự kiện thật.

Ở bước chẩn đoán ban đầu, CLI công cụ ghi đã được kiểm tra bằng `--help`; chưa thu camera trực tiếp. Sau đó người dùng gửi video đã ghi. Việc đối chiếu ảnh gốc, ROI/224×224, model gốc/smile_refined và thử crop vuông đã hoàn thành; đã hiệu chỉnh trọng số và kiểm tra lại cười, ngáp, bản ONNX cùng các lỗi mắt cũ. Số đo cập nhật nằm trong báo cáo được liên kết ở đầu tài liệu.
