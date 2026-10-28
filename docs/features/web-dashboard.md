# Web dashboard

## Đã triển khai

React/TypeScript/Vite, giao diện tiếng Việt, ba phần Giám sát – Lịch sử phiên – Kết nối.
Camera hiển thị ảnh annotated từ runtime. Biểu đồ 60 giây tách mắt 1, mắt 2 và ngáp thành hàng
để không chồng tín hiệu. Thiếu probability tạo khoảng trống; giữ label/raw/filtered đúng nguồn.
History lọc phiên/thời gian, xem event/series và xuất CSV. Không tự tính blink/yawn/alarm trên web.

## Hợp đồng kết nối

- Web build nằm ở `frontend/web/dist`, được Python phục vụ cùng origin; Radxa không cần Node.js.
- HTTPS server được shared client chấp nhận và chuyển sang WSS khi cần.
- Tình trạng quá 2 giây không có snapshot phải hiển thị mất kết nối/dữ liệu cũ.
- Live preview ưu tiên mới nhất, không tạo queue ảnh cũ hoặc làm chậm AI.
- Mã kết nối bảo vệ dữ liệu/camera; vào được trang HTML không đồng nghĩa đã xác thực API.

## Phần chưa có

PWA manifest/service worker/Web Push chưa được tích hợp. Tailscale hoặc Cloudflare chỉ cung cấp
đường truy cập; chúng không tự tạo push alert khi khóa màn hình.
Xem [remote-access](remote-access.md) trước khi làm tính năng mới này.

## Kiểm tra khi sửa UI/client

```powershell
npm.cmd run test:clients
npm.cmd run typecheck
npm.cmd run build:web
```

Đổi layout/interaction kiểm thêm `npm.cmd run test:web` và xem giao diện trong browser.
Ghi rõ mock/browser tại PC khác với iPhone thật hoặc mạng di động.
Các benchmark cũ có ngày và điều kiện trong [DASHBOARD](../../DASHBOARD.md); đo lại trên Radxa
trước khi tuyên bố đạt tốc độ hoặc p95 LAN/Internet.
