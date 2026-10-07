# Sửa cười nhe răng bị tính là ngáp — 06/10/2026

Profile camera PC đã chuyển sang `models/smile_refined/manifest.json`. Màn hình bỏ chữ R/L ở khung mắt và các dòng chẩn đoán; giữ khung, hai xác suất mắt, `Blink both` và tổng số chu kỳ đóng–mở từng mắt. Nhật ký vẫn giữ dữ liệu từng mắt.

## Lỗi tái hiện và nguyên nhân

Ảnh người dùng cung cấp cho thấy cười nhe răng nhưng classifier cho P(ngáp) 0,84, xác suất lọc 0,90 và tăng bộ đếm. Ảnh này không có file pixel riêng trong workspace, nên chưa chạy đối chiếu trực tiếp đúng ảnh đó.

Ba ảnh cười có nhãn từ SMILEs được lưu cùng nguồn/checksum trong `tests/fixtures/smiles/source.json`. Đây là các ca tái hiện lấy từ phần train, không dùng làm bằng chứng kiểm thử độc lập. Trước sửa, P(ngáp) của cả ba >0,99999; giữ ảnh 2 giây ở 15 FPS qua classifier thực và Monitor thực đều tăng 1 lần ngáp. PyTorch và ONNX cùng tái hiện lỗi, loại trừ lỗi riêng ở bước chuyển ONNX trong các ca này.

Ba giả thuyết được kiểm tra: thiếu ví dụ âm là cười; khác biệt giữa ảnh huấn luyện và vùng mặt cắt khi chạy; sai preprocessing/chuyển đổi. Việc bổ sung ảnh cười và huấn luyện trên vùng mặt runtime cải thiện rõ kết quả, trong khi preprocessing/thứ tự lớp giữ nguyên. Đây là bằng chứng lỗi khả năng khái quát hóa của classifier; các phép đo chưa tách riêng mức đóng góp của dữ liệu cười và dữ liệu crop.

## Thay đổi model và chia dữ liệu

- Giữ YOLOv8n classification, RGB 224×224, hai nhãn `no_yawn`, `yawn` và pipeline YuNet. Chỉ huấn luyện lại Linear 1280→2 của model ngáp; so sánh checkpoint xác nhận chỉ `model.9.linear.weight` và `.bias` thay đổi. Backbone, BatchNorm và model mắt giống bản gốc. Số tham số và lượng tính toán không đổi.
- Dữ liệu ngáp cũ: 1.111 train, 122 validation, 215 test. Train dùng ảnh gốc, crop YuNet với margin 10% và phiên bản xám của cả hai lớp để tránh dùng màu làm dấu hiệu thay thế nhãn. Face/eye quality của phép so sánh dùng cùng profile PC, ngưỡng mặt 20, mắt 6. Crop không đạt ở validation/test tính là UNKNOWN/bỏ sót.
- Bổ sung **chỉ các ảnh có nhãn cười**: 3.690 từ [SMILEsmileD/SMILEs](https://github.com/hromi/SMILEsmileD/tree/6afac66f50061948eed7da5a351cecd9c4a99fe3/SMILEs/positives), 2.162 từ [The MPLab GENKI Database, GENKI-4K Subset](https://mplab.ucsd.edu/398/). Không tự gán tất cả ảnh “không cười” thành “không ngáp”. GENKI dùng crop YuNet khi tìm được vùng mặt; ảnh không tìm được vùng mặt dùng trực tiếp và báo riêng. SMILEs là ảnh mặt xám đã cắt, 64×64.
- SMILEs chia theo SHA256: train 2.545, validation 563, test 582. GENKI sau bỏ 3 ảnh có đầu vào trùng nhau giữa các split: train 1.516, validation 322, test 316. Loại ảnh trùng ưu tiên giữ test, sau đó validation. Chia theo hash ngăn trùng chính xác; **chưa chứng minh độc lập theo người**, không loại hết các ảnh gần giống nhau.
- Trích feature bằng backbone đóng băng; cân bằng loss theo nguồn/lớp. Seed 42, Adam lr 0,005; thử regularization 0/0,001/0,01/0,1 và các mốc 25/50/100/150/200. Chọn bằng validation, có điều kiện bảo toàn F1/recall ngáp và F1 ảnh gốc. Chốt mốc 100, regularization 0; lưu checkpoint/manifest trước khi báo kết quả test. `validation.json` lưu các phép thử.

## Kết quả ảnh giữ riêng

Các xác suất dưới đây được kiểm tra lại từ pixel thật bằng ONNX, không chỉ tính từ feature cache. “Nhầm ngáp” là P(ngáp) ≥0,70 trên một ảnh; **không phải số báo động hoặc sự kiện trên video**.

| Phép đo | Model gốc | Model mới |
|---|---:|---:|
| 316 ảnh cười màu GENKI, nhầm ngáp | 39/316 (12,34%) | 2/316 (0,63%) |
| Trong đó 172 ảnh có face/eye quality đạt profile PC | 37/172 | 0/172 |
| 582 ảnh cười xám SMILEs đã cắt, nhầm ngáp | 581/582 | 0/582 |
| F1 lớp ngáp, 215 ảnh ngáp/không ngáp cũ qua crop runtime | 91,37% | 96,62% |
| Macro-F1 cùng 215 ảnh qua crop runtime | 92,82% | 97,62% |
| Recall ngáp tại P ≥0,70, cùng tập crop | 83,02% | 94,34% |
| Macro-F1 trên ảnh gốc chưa cắt, cùng 215 ảnh | 99,53% | 99,53% |

Cùng tập crop có 6 UNKNOWN ở cả hai model, tính vào bỏ sót. Các số model gốc ở đây khác báo cáo crop cũ do cùng dùng ngưỡng mắt 6 của profile PC hiện tại. Hai ảnh GENKI còn bị nhầm đều thuộc nhóm không đạt điều kiện face/eye quality của runtime. Ảnh SMILEs 64×64 kiểm tra khả năng của classifier trên crop, không đại diện cho toàn pipeline camera vì nhỏ hơn điều kiện mặt tối thiểu.

PyTorch→ONNX đạt 100% đồng thuận nhãn trên ảnh crop ngáp và 898 ảnh cười giữ riêng; sai khác xác suất tối đa tương ứng 1,11×10⁻⁶ và 1,22×10⁻⁶. F1 không giảm trong chuyển đổi này. Bằng chứng: `reports/yawn_smile_refined_parity.json`, `reports/smile_refinement_pixels.json`, `models/smile_refined/evaluation.json`.

## Kiểm thử runtime

- 50 test package `driver_monitor` và 2 test tương thích bản PC đạt. Có test classifier/Monitor thực: cười giữ lâu không tăng ngáp, ngáp thật vẫn xác nhận; các test blink, dữ liệu thiếu, khoảng frame, serial và tắt còi khi mất liên lạc vẫn đạt.
- Camera 0 chạy 147 frame trong 10,016 giây: **14,68 FPS**, p95 từ đọc frame đến quyết định **32 ms**, 116 NORMAL/31 UNKNOWN do mắt chưa chắc chắn, không lỗi thiết bị. Log `reports/smile_camera_check/20261006T144005_962645Z.*`. Không có gán nhãn hành vi trong lần đo này; không dùng để tuyên bố đã sửa đúng nụ cười của người dùng hoặc độ chính xác sự kiện.
- Video fixture chạy đủ 135 frame, xác nhận 1 đợt ngáp, không lỗi; log `reports/smile_video_check/20261006T144155_697559Z.*`. Đây là video ghép lặp ảnh tĩnh, chưa phải kiểm thử ngáp/cười tự nhiên theo thời gian.
- `report_assets/hud_without_eye_labels.png` đã kiểm tra trực quan, không còn nhãn R/L. Hai khung mắt và các số blink/yawn vẫn hiển thị.

## Chạy lại và tái lập

Thoát phiên cũ bằng Q/Esc trước khi chạy:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display
```

`scripts/start_camera.cmd` cũng dùng profile mới. Đối chiếu model gốc bằng cách thêm `--manifest models/manifest.json`; các ngưỡng camera vẫn theo cùng profile.

Tái lập từ dữ liệu công khai và checkpoint gốc:

```powershell
& '.\.venv\Scripts\python.exe' tools/fetch_smile_negatives.py
& '.\.venv\Scripts\python.exe' tools/fetch_genki_smiles.py
& '.\.venv\Scripts\python.exe' tools/refine_yawn_head.py prepare
& '.\.venv\Scripts\python.exe' tools/refine_yawn_head.py train --output models/smile_refined_rebuild
& '.\.venv\Scripts\python.exe' tools/check_smile_regression.py
& '.\.venv\Scripts\python.exe' tools/evaluate_smile_refinement.py
```

SMILEsmileD commit `6afac66f50061948eed7da5a351cecd9c4a99fe3`, SHA256 archive `7222201be0797c759dd248bd62bc33fe4d1334a7a703e7052ab00c04bb096e3b`. GENKI archive SHA256 `74776c0a3fac07f1cefc5d8acebf55a71fc870babc68c6b044a87d811b6de999`. Nguồn, checksum và nhãn từng ảnh nằm trong `.cache/smiles/source.json`, `.cache/genki/source.json`; feature/record cache trong `.cache/yawn_refinement/`.

## Giới hạn bàn giao

Đây là bản sửa thử PC có kết quả ảnh tĩnh tốt hơn. Cần video có nhãn cười, nói chuyện, ngáp và hoạt động bình thường của người dùng/các người test trước khi nghiệm thu; chưa có số báo nhầm/giờ, sự kiện ≥30 hoặc kiểm tra 2 giờ. Camera đo được 14,68 FPS, chưa chứng minh mục tiêu ≥15 FPS trên Radxa.

Model mới có `.pt`/`.onnx` trong `models/smile_refined/`; chưa có RKNN cho weights mới. Các RKNN/gói Radxa gốc vẫn ứng với manifest gốc. Cần chuyển manifest mới sang RK3576 trên Linux, đo tương đương và suy luận thật trên ROCK 4D sau khi bo được cài đặt. Báo cáo kiến trúc trước đây mô tả checkpoint gốc; topology mới giống hệt, nguồn dữ liệu và weights của Linear đã thay đổi như ghi ở đây.
