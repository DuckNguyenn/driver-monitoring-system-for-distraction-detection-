# Bản duyệt sơ đồ hệ thống - 14/11/2026

Phạm vi: thiết kế Chương 3, Radxa ROCK 4D/RK3576, ESP32-IDF và web; không đưa app mobile vào báo cáo. Chưa thay Word hoặc đổi model/code/ngưỡng. PC là môi trường thử riêng, không vẽ thành một thiết bị triển khai thứ hai.

Profile tham chiếu: `models/yawn_kaggle_near_medium/runtime.yaml`. Candidate pose và nhánh kính không được mặc định hóa. Sơ đồ mô tả thiết kế phần mềm, không chứng minh nghiệm thu NPU, âm thanh còi hay hiệu năng thực.

## 01. 01  Kiến trúc tổng thể

Nguồn đối chiếu: `driver_monitor/runtime.py`, `esp32_buzzer_idf/README.md`, `docs/features/radxa.md`.

## 02. 02  Một chu kỳ giám sát

Nguồn đối chiếu: `driver_monitor/runtime.py`, `driver_monitor/core.py`, `driver_monitor/vision.py`.

## 03. 03  Từ khung hình đến vùng quan tâm

Nguồn đối chiếu: `driver_monitor/vision.py`, `models/yawn_kaggle_near_medium/runtime.yaml`.

## 04. 04  Hai nhánh phân loại AI

Nguồn đối chiếu: `driver_monitor/runtime.py`, `driver_monitor/models.py`, `models/yawn_kaggle_near_medium/manifest.json`.

## 05. 05  Từ trạng thái mắt đến blink

Nguồn đối chiếu: `driver_monitor/eye_events.py`, `driver_monitor/core.py`, `models/yawn_kaggle_near_medium/runtime.yaml`.

## 06. 06  Xác nhận một đợt ngáp

Nguồn đối chiếu: `driver_monitor/core.py`, `models/yawn_kaggle_near_medium/runtime.yaml`.

## 07. 07  Chọn trạng thái và điều khiển cảnh báo

Nguồn đối chiếu: `driver_monitor/core.py`, `docs/features/monitoring.md`.

## 08. 08  Cảnh báo qua ESP32

Nguồn đối chiếu: `driver_monitor/alerting.py`, `docs/features/esp32-alerts.md`, `esp32_buzzer_idf/README.md`.

## 09. 09  Web giám sát và nhật ký

Nguồn đối chiếu: `driver_monitor/runtime.py`, `docs/features/api-history.md`, `docs/features/web-dashboard.md`.

## Đối chiếu hình cũ

3-1 → 01; 3-2 → 02; 3-3 → 03; 3-4 → 04; 3-5 → 07; 3-6 → 08; 3-7 → 09. Hai hình 05 và 06 tách riêng chi tiết mắt/ngáp, đề xuất chèn cạnh phần quyết định thời gian.

Hình 03-04 là sơ đồ xử lý, không thay các ảnh khuôn mặt minh họa đã được người dùng chỉnh nếu chưa được duyệt. Ở hình 07, UNKNOWN ưu tiên trước luật cảnh báo; minh họa mắt không đủ tin cậy không có nghĩa bằng chứng ngáp hợp lệ bị xóa.

Màu xanh lam: dữ liệu/xử lý; xanh lá: kết quả/nhánh hợp lệ; vàng: điều kiện/cảnh báo sớm; đỏ: ALERT/còi; xám: UNKNOWN hoặc đường dự phòng. Nhãn chữ vẫn giải thích ý nghĩa khi in đen trắng.

Đề nghị duyệt: bố cục, độ dễ đọc, mức chi tiết; sau khi chốt mới chèn vào Word và đánh lại số hình.
