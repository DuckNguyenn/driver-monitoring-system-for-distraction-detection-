# Giao diện app Android / iPhone

## Phạm vi

UI React Native dùng chung hai nền tảng; bản Android mới là 1.1.0 (versionCode 2).
Không đổi API, model, preprocessing, ngưỡng cảnh báo hay camera/serial runtime.
Quyền, APK và foreground lifecycle xem [Android](android.md), [iPhone](iphone.md).

## Thiết kế và luồng sử dụng

- Nền sáng, xanh đậm cho nhận diện; đỏ/vàng/xám theo trạng thái có chữ và icon đi kèm.
- Header hiển thị trạng thái kết nối thật; ba tab cố định Giám sát, Lịch sử, Kết nối.
- Chữ nội dung 14px trở lên, caption 11–13px; ô nhập/nút chính cao tối thiểu 48px.
- Kết nối: hai bước địa chỉ máy chủ và mã; focus viền rõ, Next sang mã, có hiện/ẩn mã.
  Kiểm tra API trước khi lưu SecureStore; nút hiển thị tiến trình và khóa khi đang gửi.
- Giám sát: trạng thái tài xế, ảnh camera, hai bộ đếm, biểu đồ, thiết bị và chất lượng.
  Có trang rỗng với nút kết nối; preview có nhãn nguồn trực tiếp/phát lại.
- Lịch sử: tìm mã/nguồn trong trang hiện tại; bộ lọc ngày có thể mở/đóng.
  Chạm phiên để mở chi tiết; nút quay lại danh sách, biểu đồ/sự kiện và chia sẻ CSV.
- Khi đổi tab hoặc mở/đóng chi tiết phiên, cuộn về đầu để nội dung cần xem luôn hiện rõ.
- Các icon là SVG trong source; không thêm thư viện/font hay ảnh tải từ bên ngoài.

## Hợp đồng dữ liệu phải giữ

- App nhận quyết định từ PC/Radxa. Không suy diễn từ hình ảnh hay tô trạng thái tốt khi mất dữ liệu.
- Thiếu bằng chứng vẫn UNKNOWN/null, hiển thị dấu —; biểu đồ ngắt khi thiếu mẫu hoặc gián đoạn nguồn.
- Ba biểu đồ Mắt 1, Mắt 2, Ngáp dùng cùng cửa sổ 60 giây; không gộp hai mắt thành một đường.
- Blink hai mắt, chu kỳ một mắt và ngáp xác nhận có nhãn riêng; vẫn giữ P(ngáp) thô.
- Mất kết nối: dữ liệu gần nhất được ghi rõ và làm mờ; preview dừng/không giữ ảnh như ảnh live.
- LivePreview giữ cachePolicy none, PreviewStream loaded/failed và dừng khi inactive/unmount.
- ALERT foreground theo danh tính đợt; giữ AlertMemory/SecureStore để tránh rung lặp.
  Video phát lại không kích hoạt rung/banner camera. Chưa có cảnh báo nền/khóa màn hình.
- Lịch sử giữ HistoryReader chống request cũ ghi đè, phân trang server và xuất CSV hiện có.

## Source theo trách nhiệm

| File trong frontend/mobile | Trách nhiệm |
|---|---|
| App.tsx | Lifecycle, SecureStore, kết nối live, banner và điều hướng |
| components/ui.tsx, Icon.tsx | Màu sắc, card/button/badge/empty state, icon |
| components/ConnectionCard.tsx | Hai bước kết nối và bàn phím/mã bảo mật |
| components/Monitor.tsx | Trạng thái, bộ đếm, thiết bị và chất lượng |
| components/LivePreview.tsx | JPEG và lifecycle PreviewStream |
| components/SignalChart.tsx | Ba biểu đồ cùng trục thời gian |
| components/History.tsx | Danh sách, bộ lọc, chi tiết/sự kiện và CSV |

Context pack UI gồm đúng 12 file; không nạp toàn bộ backend để sửa bố cục.
API contract xem [api-history](api-history.md); không đưa mã API hoặc hình cá nhân vào docs.

## Kết quả kiểm tra ngày 2026-10-15

- APK1.1.0/code2 đã cài cập nhật trên LDPlayer 9, không xóa dữ liệu app.
- Đã xem ảnh/thao tác native ở617dp và360dp; trả density giả lập về280 sau thử.
- Kết nối/hiện-ẩn mã, NORMAL/UNKNOWN/ALERT, preview, biểu đồ, history/detail/filters/CSV đạt với fixture.
- Đã sửa nền tab active mất bo góc bằng remount riêng pill theo selected; không đổi hit target.
- Mất API hiển thị trạng thái cũ rõ ràng; API thử đã dừng và kết nối fixture đã bỏ qua nút Ngắt.
- TypeScript,10 client tests,18 test build/docs, iOS export và APK release đã đạt.
- Chưa thử camera/rung/khóa màn hình trên điện thoại thật; các ảnh và số liệu test là tổng hợp.

## Kiểm tra

```powershell
npm.cmd run test:clients
npm.cmd run typecheck
npm.cmd run export:android
npm.cmd run build:android
.\.venv\Scripts\python.exe tools/check_repo_docs.py
```

Kiểm tra APK trực tiếp trên LDPlayer: ô nhập/focus/ẩn-hiện mã, mã sai/đúng, tabs,
NORMAL/ALERT/UNKNOWN, preview, null/chart gaps, history/detail/back, bộ lọc/CSV và API reconnect.
Thử ảnh/status tổng hợp không chứng minh độ chính xác model, camera hoặc rung điện thoại thật.
Bằng chứng UI: [mobile-ui-validation](../evidence/2026-10-15-mobile-ui-validation.json).
