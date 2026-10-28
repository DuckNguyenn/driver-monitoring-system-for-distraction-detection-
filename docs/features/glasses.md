# Nhánh mắt có kính

## Yêu cầu đã chốt

Kính cận/trong suốt; tự nhận kính và chuyển model mắt. Giữ nhánh mắt không kính và ngáp của
profile gốc. Người dùng chưa cung cấp video RGB có kính được gán nhãn độc lập.

## Đã có trong code và candidate

- `--auto-glasses` opt-in; mặc định giữ original.
- Selector MobileNetV3-Small RGB128, ONNX CPU, manifest riêng `models/eyewear_selector/manifest.json`.
- Nhánh mắt `models/eye_glasses_adapted/manifest.json` được fine-tune từ MRL IR.
- Gate yêu cầu điểm cao đủ lâu, reset khi stale/gap/mất mặt/đổi track; lỗi fallback original.
- Chuyển nhánh ngắt xác nhận mắt của frame đó, không sở hữu hoặc gọi lại model ngáp.
- Bằng chứng PC từng ghi nhận parity selector/candidate và replay bốn clip không kính không đổi
  kết quả. Điều này không chứng minh kính RGB ngoài camera thực đã tốt hơn.

## Những gì chưa đạt

- Thiếu video RGB có kính thật và nhãn mắt đã review; chưa có kết quả live RGB glasses.
- IR có cải thiện F1 nhưng có trade-off false closed/UNKNOWN; không áp dụng specialist toàn cục.
- Không dùng ảnh nhãn “eyeglasses” như bằng chứng Open/Closed hoặc kính luôn trong suốt.
- Bộ ZIP Radxa hiện tại chưa đóng gói hai artifact của auto-glasses.
- Mục tiêu độ chính xác có kính còn bị chặn bởi dữ liệu, không hoàn thành chỉ nhờ test phần mềm.

## Workflow chỉ mở khi có video

[RGB_WORKFLOW](../../data_collection/eye_glasses/RGB_WORKFLOW.md): quay video → gán nhãn tay →
build crop đúng runtime → static/replay đánh giá → bổ sung GPU train nếu đủ split độc lập.
Video test đã giữ riêng không được chuyển sang train để làm đẹp kết quả.

Hồ sơ cục bộ: `reports/glasses_adaptation_20261013/progress.json` và thư mục `automatic_routing/`.
Hai job Kaggle IR specialist/selector trước đã COMPLETE; không polling lại nếu không có job mới.

## Kiểm tra

```bash
python -m unittest tests.test_eyewear tests.test_glasses_training tests.test_eye_glasses_rgb_evaluation -v
```

Task thay routing cần replay không kính và khẳng định model ngáp không đổi; task dữ liệu cần
kiểm tra nhãn, timestamp, hash và tách theo người trước khi yêu cầu train.
