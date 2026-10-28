# Truy cập từ xa và thông báo iPhone

## Trạng thái và mong muốn

Người dùng muốn xem camera và nhận cảnh báo khi không cùng LAN, ưu tiên miễn phí.
Người dùng xác nhận 2026-10-15: chưa setup Tailscale trên Radxa/iPhone và yêu cầu để sau.
Windows đã kiểm tra lại `Running`/online; chưa thấy peer Radxa/iPhone.
SSH tới LAN cũ `192.168.2.38:22` bị timeout; chưa kiểm chứng truy cập từ xa.
Cloudflare Quick Tunnel đã được giải thích như lựa chọn thử; chưa có tunnel được kiểm chứng.
Thông báo khi iPhone khóa màn hình/app ở nền vẫn là tính năng cần phát triển.

## Truy cập: đường đi hiện có

Camera → AI/Monitor trên Radxa → API serve → mạng Tailscale hoặc HTTPS tunnel → web/app.
AI không chạy trên điện thoại hoặc Cloudflare. ESP32/buzzer vẫn là nhánh cảnh báo tại chỗ.
API/client hiện có đã nhận địa chỉ HTTPS/WSS, nhưng dòng mô tả UI vẫn thiên về LAN.

### Khi người dùng chọn tiếp tục Tailscale

Windows dùng `C:\Program Files\Tailscale\tailscale.exe`; chưa thấy peer hostname radxa/rock-4d
khi kiểm lần cuối. Không lấy IP Windows làm URL của API đang chạy trên bo.

Trên Radxa, nếu chưa cài/đăng nhập:

```bash
sudo apt install -y curl
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Mở URL xác thực vừa in và chọn cùng tailnet đang dùng trên Windows; không chép URL dùng một lần
vào checkpoint. Trên iPhone cài Tailscale, đăng nhập cùng mạng và cho phép cấu hình VPN.

Sau đó trên bo:

```bash
tailscale ip -4
tailscale status
```

Dùng IP thật vừa in với cổng 8765 trong web/app; giữ serve đang chạy và nhập mã API của serve.
Thử iPhone bằng 4G trong khi Tailscale vẫn Connected, ghi kết quả ảnh/status và reconnect.
Radxa trên xe vẫn cần Internet, chẳng hạn Wi-Fi từ bộ phát hoặc điện thoại.

### Cloudflare khi chọn lại phương án tunnel

Quick Tunnel dùng `cloudflared tunnel --url http://127.0.0.1:8765`; có URL HTTPS tạm,
không cần tên miền/tài khoản để thử, hostname thay đổi khi tạo lại. Named tunnel là triển khai khác.
Mã nhập app là mã API hiện có, không phải token cloudflared hoặc mật khẩu SSH.

## Thông báo khóa màn hình: chưa có code

- WebSocket + haptics foreground không tự trở thành push nền.
- Bản native riêng cần đăng ký token/APNs/credentials và kiểm thử theo môi trường build.
- Hướng miễn phí đề xuất: dashboard PWA qua HTTPS, thêm vào Home Screen iOS 16.4+, Web Push.
  PWA nhận thông báo riêng với bản Expo Go; chưa có manifest/service worker/push API trong repo.
- Khi triển khai: lấy ALERT từ Monitor, một đợt một event id; đăng ký subscription có xác thực,
  gửi bất đồng bộ, lưu retry/TTL, loại subscription hết hiệu lực, ngăn gửi trùng khi reconnect.
- Bật permission từ thao tác người dùng. Test app đóng/màn hình khóa, 4G, mất mạng và bấm notification.
- Cần đo delivery thực; push receipt không chứng minh người nhận đã đọc hoặc mọi sự cố đều được phát hiện.

## Nguồn chính thức và test

- [Tailscale Linux](https://tailscale.com/docs/install/linux), [iPhone](https://tailscale.com/docs/install/ios).
- [Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
- [WebKit: Home Screen Web Push](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
- `npm.cmd run test:clients`; `python -m unittest tests.test_dashboard_api -v`.

Checkpoint và IP/process còn hiệu lực phải được xác minh lại khi chuyển chat/mạng.
