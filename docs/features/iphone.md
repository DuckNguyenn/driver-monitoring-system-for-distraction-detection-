# App iPhone

Bố cục/màu/luồng app mới xem [mobile-ui](mobile-ui.md).

## Đã có

React Native + Expo + TypeScript, thử bằng Expo Go. Kết nối lưu bằng SecureStore.
Dùng chung mã nguồn với [app Android](android.md); hướng dẫn APK nằm tại feature Android.
App nhận status, probability, history và annotated JPEG; ảnh dùng expo-image với Bearer header,
không cache live frame. AppState điều khiển việc theo dõi foreground và yêu cầu preview.
Đợt ALERT mới tạo banner/rung một lần; giữ danh tính đợt cảnh báo qua reconnect để tránh báo lặp.

## Kết nối đúng thiết bị

Nhập server chạy `serve`: IP LAN hoặc IP Tailscale của Radxa/PC đó, hoặc HTTPS hostname thật.
`127.0.0.1`/localhost trên iPhone trỏ vào iPhone. IP Tailscale Windows không tự là IP của Radxa.
Native app dùng mã API của serve; token cloud/VPN không thay mã này.
Qua Tailscale, iPhone phải kết nối cùng tailnet và server phải đang hoạt động.

## Cảnh báo và giới hạn hiện tại

- Người dùng hiện dùng Expo Go, chưa có bản iOS riêng/TestFlight.
- Banner/haptics đang được thực hiện khi app hoạt động foreground.
- Chưa có expo-notifications, đăng ký push token, APNs/EAS credentials hoặc background push.
- Khả năng nhận thông báo khóa màn hình chưa được triển khai/kiểm chứng.
- Hướng miễn phí đã được đề xuất là PWA + Web Push; đó là web app trên Home Screen,
  cần implementation riêng và không được ghi thành chức năng native Expo Go đã có.

## Kiểm tra

```powershell
npm.cmd run test:clients
npm.cmd run typecheck
npm.cmd exec --workspace=@driver-monitor/mobile -- expo-doctor
```

Test iPhone thật cần quan sát quyền local network/VPN, mất mạng, khóa/mở app và reconnect.
Expo export/typecheck không chứng minh app đã cài hoặc notification đã đến màn hình khóa.
Runbook: [DASHBOARD](../../DASHBOARD.md), [remote-access](remote-access.md).
