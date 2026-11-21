# Thử model ngáp fine-tune ngày 18/11/2026

Fine-tune tiếp từ model near/medium hiện hành, bổ sung 95 crop đã rà từ camera Radxa DV20 và giữ 735 ảnh cũ. Chỉ đầu phân loại được cập nhật. Kaggle Tesla T4 chạy 15 epoch, chọn epoch 7. ONNX đã kiểm tra trên laptop; chưa thử trên phần cứng Radxa.

Trên clip đã dùng train: bộ đếm 1 → 6, giữ nguyên ngưỡng. Kết quả này không phải độ chính xác trên dữ liệu độc lập. Cần thử thêm một phiên camera mới, gồm ngáp, bình thường, nói chuyện và cười.

## 1. Chép từ laptop sang Radxa

Chạy trong **PowerShell Windows**, không chạy trong terminal có dấu nhắc `root@radxa`:

```powershell
scp -r "C:\Users\P1 Gen 5\Downloads\DA2\models\yawn_radxa_20261118_candidate" root@192.168.137.147:/root/DA2/models/
```

Địa chỉ trên là IP Radxa gần nhất trong phiên làm việc; thay nếu IP đã đổi. Nhập mật khẩu SSH trực tiếp trong terminal khi được yêu cầu.

## 2. Chạy camera realtime trên Radxa

Trong terminal SSH của Radxa, dừng phiên nhận diện cũ bằng Ctrl+C, rồi chạy:

```bash
cd /root/DA2
.venv/bin/python -m driver_monitor serve --config models/yawn_radxa_20261118_candidate/runtime.yaml --source /dev/video0 --backend onnx --host 0.0.0.0 --port 8765 --preview-fps 5
```

Mở giao diện web như trước và dùng mã kết nối phiên mới. Camera được xử lý trực tiếp; lệnh không quay clip để phát lại.

Model mắt và YuNet dùng các file sẵn có trong project. Không chạy đồng thời hai phiên trên cùng camera. Lệnh trên chưa bật cổng ESP32.

## 3. Thử và đối chiếu

- Thử vài động tác ngáp, sau mỗi lần trở về bình thường khoảng 2 giây để quan sát trạng thái hết ngáp.
- Thử nói chuyện, cười và chỉ hé miệng; ghi lại nếu bộ đếm tăng nhầm.
- Xem cả `P raw`, `P filtered`, trạng thái chất lượng và số lần ngáp; không chỉ nhìn một ảnh tức thời.
- Ảnh mờ/thiếu bằng chứng vẫn giữ UNKNOWN. Không hạ bộ lọc hoặc ngưỡng để ép nhận diện.

## 4. Quay lại model trước

Dừng bằng Ctrl+C rồi dùng lại cấu hình cũ:

```bash
cd /root/DA2
.venv/bin/python -m driver_monitor serve --config models/yawn_kaggle_near_medium/runtime.yaml --source /dev/video0 --backend onnx --host 0.0.0.0 --port 8765 --preview-fps 5
```

Bản cũ được giữ nguyên. Nếu đang dùng cấu hình riêng trên Radxa trước đợt này, chọn lại đúng cấu hình đó.
