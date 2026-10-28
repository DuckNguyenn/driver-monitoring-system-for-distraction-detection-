# Dữ liệu và huấn luyện

## Phạm vi

Người dùng ưu tiên GPU Kaggle/Colab; PC dùng chuẩn bị dữ liệu, replay, export/parity và kiểm tra.
Nguồn checkpoint gốc từ người dùng đã train; candidate chỉ được đánh giá như fine-tune tiếp.
Đợt yawn near/medium đã hoàn thành Kaggle và có profile riêng; far chưa được coi là đã đạt.
Nhánh multiview thử nghiệm có kết quả riêng, không được tự đẩy thành model đang dùng.

## Hợp đồng dữ liệu

- Lưu video gốc, timestamp thực, subject_id/capture_group/split và ảnh crop native.
- Crop/resize theo cùng đường runtime; downsample trước resize 224×224, blur nhẹ trong train.
- Bổ sung mắt mở/nhắm, nói chuyện, cười, kính và các góc camera có nhãn thật.
- Prompt quay video và dự đoán model không thay nhãn đã review bằng mắt người.
- Tách theo người/clip/capture group; một frame/ảnh trùng không được đi qua các split.
- Chỉ chọn checkpoint/ngưỡng bằng validation rồi khóa trước test độc lập.
- Khác biệt IR và RGB phải được báo rõ. Development replay không trở thành test trên người mới.

## Đánh giá và giới hạn

F1/precision/recall/confusion matrix cần kèm số mẫu, split, điều kiện, confidence gate và UNKNOWN.
Ngáp theo sự kiện cần nhãn thời gian, không suy ra event recall từ accuracy từng ảnh.
Ảnh mở miệng/cười và clip đổi khoảng cách là các hard case phát triển đã biết.

## Runbook chỉ mở khi làm cloud/data

- [Kaggle/Colab và credential](../../CLOUD_TRAINING.md).
- [Thu yawn theo khoảng cách](../../data_collection/yawn_distance/README.md).
- [Dữ liệu chung](../../data_collection/README.md).
- [Nhánh kính RGB đang thiếu video](glasses.md).

Token cloud chỉ lưu tại máy; không đưa vào notebook, repo, log hoặc checkpoint.

## Kiểm tra

```bash
python -m unittest tests.test_yawn_training_validation tests.test_yawn_distance_training tests.test_yawn_kaggle_bundle -v
```

GPU job, dataset upload và kết quả chỉ ghi đã chạy khi có bằng chứng thật; ghi rõ những job lịch sử
đã COMPLETE để chat mới không tiếp tục polling hoặc train CPU lại.
