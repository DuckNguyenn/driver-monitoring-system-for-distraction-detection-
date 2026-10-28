# Bản đồ context và feature

Một miền giám sát tài xế, nhiều feature. [Thuật ngữ chung](CONTEXT.md) là glossary;
tài liệu feature giữ hợp đồng và cách kiểm chứng. Bắt đầu từ [CHECKPOINT](CHECKPOINT.md).

## Chọn đúng nhánh

| Feature | Khi cần đọc |
|---|---|
| [runtime](docs/features/runtime.md) | Vòng xử lý camera/video, cấu hình, đóng tài nguyên và log |
| [vision](docs/features/vision.md) | YuNet, crop mắt/mặt, chất lượng ảnh, chuyển động và camera USB |
| [monitoring](docs/features/monitoring.md) | Logic thời gian, blink, eye cycle, ngáp, NORMAL/WARNING/ALERT/UNKNOWN |
| [models](docs/features/models.md) | Manifest, preprocessing, classifier torch/ONNX/RKNN và chọn profile |
| [training](docs/features/training.md) | Thu/gán nhãn, fine-tune Kaggle/Colab, blur và gần–trung bình |
| [glasses](docs/features/glasses.md) | Tự nhận kính, chuyển nhánh mắt và đánh giá RGB có kính |
| [esp32-alerts](docs/features/esp32-alerts.md) | Serial ACK, heartbeat, watchdog ESP32 và buzzer |
| [api-history](docs/features/api-history.md) | FastAPI, snapshot, WebSocket, preview và SQLite/history |
| [web-dashboard](docs/features/web-dashboard.md) | React dashboard, camera, biểu đồ riêng từng tín hiệu, history/CSV |
| [iphone](docs/features/iphone.md) | React Native/Expo Go, kết nối, preview và cảnh báo foreground |
| [mobile-ui](docs/features/mobile-ui.md) | Bố cục/màu/icon, màn kết nối, giám sát và lịch sử Android/iPhone |
| [android](docs/features/android.md) | Android Expo/APK, kết nối LAN, camera, lịch sử và rung foreground |
| [radxa](docs/features/radxa.md) | Đóng gói, Debian ARM64, ONNX CPU và lộ trình RKNN/RK3576 |
| [remote-access](docs/features/remote-access.md) | Tailscale/Cloudflare và yêu cầu thông báo iPhone từ xa |
| [reporting](docs/features/reporting.md) | Báo cáo Word/PDF, kiến trúc, hình và nội dung đúng scope |
| [docs-governance](docs/engineering/WORKFLOW.md) | Docs, context pack, LOC/byte guard và checkpoint |

## Ranh giới quan trọng

- Vision tạo crop/quality → classifier cho probability → Monitor quyết định theo thời gian.
- Monitor → serial ESP32 và nhật ký; API/web/iPhone nhận kết quả, không tái tính cảnh báo.
- Auto-glasses chỉ chọn nhánh mắt; model ngáp của profile giữ nguyên.
- Tailscale/Cloudflare cung cấp đường truy cập; push nền cần feature mới trên API/web/iPhone.
- Huấn luyện chọn candidate bằng validation; model/profile đang chạy là lựa chọn riêng.
- Báo cáo dùng bằng chứng đã đo; không biến roadmap hoặc smoke thành nghiệm thu.

## Đọc có giới hạn

Registry máy đọc được: [feature-map.json](docs/feature-map.json).
Danh sách file/số byte: `python tools/context_pack.py --feature remote-access`.
Thêm `--include-source --include-tests` khi cần; chỉ `--print` mới xuất nội dung.
Nếu một task vượt pack 96.000 byte/12 file, chia theo kết quả có thể test.
Quy trình đầy đủ: [context/LOC](docs/engineering/WORKFLOW.md).
