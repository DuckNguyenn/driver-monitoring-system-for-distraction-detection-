# App Android

Bố cục/màu/luồng app mới xem [mobile-ui](mobile-ui.md).

## Phạm vi

Dùng chung React Native/Expo và API với app iPhone; package Android là
`com.da2.drivermonitor`. Camera, AI/Monitor và serial/buzzer vẫn chạy trên PC hoặc Radxa.
App có kết nối bằng địa chỉ + mã API, ảnh camera có khung, trạng thái, biểu đồ, lịch sử và chia sẻ CSV.
Mã API lưu bằng SecureStore. Android rung/banner theo từng đợt ALERT khi app đang mở.
Khi vào nền, WebSocket/preview dừng; mở lại sẽ đồng bộ. Chưa có push/foreground service khi khóa màn hình.
Tailscale trên Radxa/iPhone đã hoãn theo yêu cầu; phát triển Android không cài hoặc đổi cấu hình VPN.

## Dùng trên điện thoại

1. Giữ một tiến trình `serve` chạy trên PC/Radxa, chọn đúng profile/model hiện dùng.
2. Cho Android và máy xử lý vào cùng Wi-Fi; nhập URL `http://<IP-máy-xử-lý>:8765`.
3. Nhập mã API do `serve` tạo; đây không phải mật khẩu SSH hoặc mã Expo.
4. Mở Giám sát để xem camera/trạng thái, Lịch sử phiên để xem sự kiện và chia sẻ CSV.

`localhost`/`127.0.0.1` trên điện thoại không trỏ tới PC/Radxa. Khi dùng mạng VPN sau này,
nhập IP của chính máy chạy `serve`; HTTPS cũng được client hỗ trợ.

### Thử bằng Expo Go

Cài Expo Go tương thích SDK 57 trên Android. Từ workspace Windows:

```powershell
npm.cmd run start:android
```

Mở Expo Go trên Android và quét QR trong terminal. Đây là QR tải app, khác mã API ở bước kết nối.
Giữ terminal Expo và `serve` khi thử theo cách này.

### APK cài trực tiếp

Build local tạo `dist/android/DriverMonitor.apk` và `build.json` (ABI, SHA-256, kích thước).
APK release đóng gói JavaScript nên không cần Metro/Expo Go; vẫn cần API `serve` đang chạy.
Sao chép APK sang điện thoại, mở file và cho phép ứng dụng mở file cài APK khi Android yêu cầu.
Bản local dùng khóa debug của Expo template để thử nội bộ; chưa phải bản phát hành Google Play.
ABI mặc định: arm64-v8a, armeabi-v7a và x86_64 (giả lập); minSdk của React Native hiện dùng là 24 (Android 7+).
Build thành công chưa chứng minh hoạt động camera/rung/CSV trên điện thoại thật.

## Build và kiểm tra

Máy build Windows cần Node >=22.13, dependencies npm, JDK 17+, Android SDK 36/build-tools 36.0.0,
NDK 27.1.12297006 và CMake 3.22.1. Có thể đặt JAVA_HOME/ANDROID_HOME hoặc dùng bộ portable
trong `.cache/android/jdk` và `.cache/android/sdk`; không đóng gói toolchain vào APK/tài liệu bàn giao.

```powershell
npm.cmd run test:clients
.\.venv\Scripts\python.exe -m unittest tests.test_android_build -v
npm.cmd run typecheck
npm.cmd run export:android
npm.cmd run build:android
.\.venv\Scripts\python.exe tools/check_repo_docs.py
```

Script build sinh native Android bằng Expo prebuild rồi chạy Gradle assembleRelease;
kiểm manifest cho phép HTTP trước khi build. Cảnh báo native được ghi thành log;
chỉ mã thoát khác 0 mới làm build thất bại (có test hồi quy PowerShell).
Script dùng hai ổ ảo V–Z tạm cho cache Gradle/SDK để tránh giới hạn đường dẫn của Ninja và
giữ nguyên tên clang++ trên Windows. Dữ liệu vẫn nằm trong workspace; ổ ảo được gỡ khi kết thúc.
Cache CMake được dựng lại khi đổi ổ ảo; có thể thêm `-CleanNative` khi gọi script trực tiếp. Native folder bị Git ignore và có thể sinh lại.
`eas.json` có profile preview APK nếu sau này chọn EAS; chưa có project/credentials được provision.

Android cho phép HTTP để kết nối API LAN có địa chỉ nhập động; dữ liệu HTTP nên đi trong LAN/VPN tin cậy.
App yêu cầu Internet/Vibrate, chặn quyền camera, microphone, bộ nhớ ngoài và vẽ nổi của template.
Camera trên điện thoại không được sử dụng. Ảnh xem trước lấy từ máy xử lý.

## LDPlayer

Phiên máy này dùng LDPlayer 9, Android 9, index 0; ADB đã nối tại `127.0.0.1:5555`.
APK có x86_64 để chạy trực tiếp trên giả lập. Có thể kéo APK vào LDPlayer để cài.
Trong app nhập IP LAN thật của PC/Radxa chạy serve; không dùng IP ADB làm địa chỉ API.
Chạy test UI bằng ảnh/status tổng hợp không chứng minh camera, model hoặc rung phần cứng.

### Kết quả LDPlayer ngày 2026-10-15

APK đã build/cài/mở độc lập; chạm hai ô nhập được người dùng xác nhận sau khi khởi động lại LDPlayer.
API tổng hợp trên PC đã qua: mã sai/đúng, NORMAL/ALERT, preview, placeholder null,
banner camera foreground, lịch sử/chi tiết, mở bảng chia sẻ CSV, khôi phục SecureStore và API reconnect.
Ở nền, số request ảnh giữ nguyên giữa hai lần đo (813 → 813); chưa thử mất Wi-Fi trên điện thoại thật.
Ảnh thử có nhãn SYNTHETIC / NO CAMERA; không mở camera hoặc serial.
Bằng chứng: [android-validation](../evidence/2026-10-15-android-validation.json).

Đã gặp cả giả lập không nhận chạm/phím: `dumpsys input` ghi DispatchFrozen=1,
WindowManager đang freeze khi đổi hướng; dừng riêng app không giải phóng input.
Khởi động lại đúng phiên LDPlayer đã phục hồi (DispatchFrozen=0); không xóa dữ liệu app.
Nếu lặp lại, lưu dấu hiệu này rồi khởi động lại giả lập; nguyên nhân gốc trong LDPlayer chưa được chứng minh.

## Kiểm thử thiết bị thật còn cần

- URL/mã sai, ngắt Wi-Fi và reconnect; thiếu bằng chứng giữ UNKNOWN/null.
- Camera có khung, ảnh không cache và preview ngừng khi app vào nền.
- Một đợt ALERT rung/banner một lần; quay lại app không báo trùng đợt cũ.
- Lịch sử/phân trang/chia sẻ CSV, bàn phím và thanh điều hướng Android.
- Khóa màn hình: ghi rõ chưa hỗ trợ cảnh báo nền; còi tại máy xử lý vẫn là nhánh riêng.

Xem [iPhone](iphone.md), [API](api-history.md), [remote-access](remote-access.md).
Nguồn build: [Expo APK](https://docs.expo.dev/build-reference/apk/),
[Expo local release](https://docs.expo.dev/guides/local-app-production/).
