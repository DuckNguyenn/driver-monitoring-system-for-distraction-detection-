# API giám sát và lịch sử

## Hợp đồng

FastAPI phục vụ `/api/v1`, web tĩnh đã build và WebSocket. Inference ở process riêng, status/frame
qua hàng đợi giới hạn, ưu tiên mới nhất. Snapshot là kết quả Monitor; client không tính lại alarm.
`MonitorSnapshot` giữ session/sequence/UTC/source clock, lifecycle, state/reasons, probability,
counts, quality, performance, device state và alert_episode_id. Thiếu dữ liệu giữ null.

## Xác thực và camera

- REST/JPEG dùng Bearer token; WebSocket xác thực ở thông điệp đầu trong 5 giây.
- Mã lưu tại log dir ở `.dashboard-token`, in khi serve khởi động; không đưa vào URL hoặc Git.
- Mã này khác mật khẩu SSH, token Cloudflare và token push.
- Ảnh mới nhất có khung/text như cửa sổ Driver monitor; encode bất đồng bộ, client chậm bỏ ảnh cũ.
- Frame endpoint không cache; chỉ yêu cầu ảnh khi màn hình camera được xem, dừng khi app ở nền.
- Không có API điều khiển camera/runtime hoặc chỉnh ngưỡng trong phiên bản đã triển khai.

## Lịch sử

SQLite là chỉ mục dẫn xuất tại máy từ JSONL gốc. Nhập lại không trùng; file nguồn bị thay/rút ngắn
phải được nhận diện và dựng lại chỉ mục. Phân trang history/series/events, CSV đủ dữ liệu của phiên.
Phiên video có nhãn phát lại. Dữ liệu hỏng được xử lý ở chỉ mục, không sửa bytes log gốc.

## Ranh giới sửa

Mạng/API crash không thay logic còi; shutdown đóng worker đúng hạn và cho runtime cleanup.
Giữ origin web/API đồng nhất khi dùng HTTPS tunnel. Đăng ký/gửi Web Push chưa có trong API hiện tại.

## Kiểm tra

```bash
python -m unittest tests.test_dashboard_api tests.test_dashboard_history -v
```

Đổi process/queue/preview cần thêm tests.test_dashboard_process và tests.test_dashboard_transport.
API chi tiết và runbook: [DASHBOARD](../../DASHBOARD.md).
