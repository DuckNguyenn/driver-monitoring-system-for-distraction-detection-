# Fine-tune ngáp trên Kaggle GPU

> Tiếp tục theo feature: [bản đồ context](CONTEXT-MAP.md), [checkpoint mới nhất](CHECKPOINT.md), [docs](docs/README.md).

Mục tiêu: train classifier ngáp gần/trung bình trên GPU cloud, giữ preprocessing crop/resize của runtime. Không train lại mắt/YuNet và không tự thay model đang chạy camera.

## Phiên đã setup ngày 11/10/2026

- Tài khoản CLI đã xác thực: `nguyntrnminhc`.
- [Dataset Private](https://www.kaggle.com/datasets/nguyntrnminhc/yawn-near-medium-20261011-033302): ZIP 45.803.233 byte, 735 ảnh (575 train, 160 static validation), hai checkpoint khởi đầu. Không có clip xa hoặc clip test đã khóa.
- [Notebook Private](https://www.kaggle.com/code/nguyntrnminhc/yawn-gpu-near-medium-20261011-033302): dataset đã gắn, GPU T4 ×2 được yêu cầu, Internet bật để cài dependency. Notebook dùng GPU đầu tiên, tối đa 40 epoch; phiên có giới hạn 1 giờ.
- Metadata đã tải lại từ Kaggle xác nhận `is_private: true`, `enable_gpu: true`, `machine_shape: NvidiaTeslaT4` và đúng dataset nguồn.
- Bộ CLI cloud riêng: `.venv-cloud`, Kaggle 2.2.4; dependency trong `requirements-cloud.lock.txt`. Python/torch của runtime camera không bị đổi.

Trạng thái được ghi trong `kaggle_upload/cloud/latest.json`. `RUNNING` là trạng thái worker của Kaggle; chỉ xác nhận GPU/epoch thực tế sau khi đọc được log hoặc đầu ra. Kết quả validation ảnh tĩnh và crop camera train không phải nghiệm thu camera/người độc lập. Model cloud vẫn là ứng viên thử nghiệm.

Phiên bản notebook **2 đã COMPLETE**: chạy thật trên Tesla T4, 19 epoch, chọn epoch 11 theo static validation. Backbone và BN running buffers không đổi. Gói model đã tải và giải nén riêng tại `models/yawn_kaggle_near_medium/`; profile hiện tại không tự chuyển sang model này. Môi trường thực ghi trong `validation.json`: Python 3.13.15, torch 2.11.0+cu128 và NumPy 2.1.3. NumPy đang được kernel giữ trong bộ nhớ khác pin 2.2.6 của bước cài; version thực đã được ghi lại, không coi môi trường này là tái lập tuyệt đối theo file pin.

Kiểm tra bằng runtime PC hiện tại (ONNX Runtime 1.20.1): 48 crop gần/trung bình/static, nhãn PT và ONNX đều khớp, sai lệch xác suất lớn nhất **2,2765 × 10⁻⁷**. ONNX có IR 7, opset 12. Đây là kiểm tra chuyển đổi/tương thích, chưa đo recall sự kiện hoặc cảnh báo nhầm trên camera mới. Bằng chứng: `reports/cloud_training/pc_runtime_parity.json`, `reports/cloud_training/kaggle_v2.log`, `models/yawn_kaggle_near_medium/validation.json`.

Chạy thử ứng viên trên camera trong PowerShell tại thư mục project:

```powershell
& '.\.venv\Scripts\python.exe' -m driver_monitor run --config models/yawn_kaggle_near_medium/runtime.yaml --source 0 --backend onnx --display
```

Runtime yêu cầu cạnh ngắn khung mặt đạt `min_face_size: 80` pixel trên ảnh camera gốc. Mặt đã được YuNet phát hiện nhưng nhỏ hơn ngưỡng sẽ hiển thị `UNKNOWN: face_too_small`, kèm kích thước/ngưỡng và `MOVE CLOSER`; trường hợp không có mặt hợp lệ trong vùng tài xế vẫn là `no_face`. Model mắt/ngáp không chạy trên mặt bị loại vì kích thước. Phát lại clip far `20261010T163038_149200Z.avi` ngày 11/10: cả 24 frame lấy mẫu đều được YuNet phát hiện (độ tin cậy 0,920–0,936), nhưng cạnh ngắn chỉ 70,0–78,5 pixel nên không qua ngưỡng. Đây là kiểm tra detector/bộ lọc kích thước, chưa phải đánh giá độ chính xác ngáp ở xa. Giữ ngưỡng hiện tại và điều chỉnh vị trí camera; dữ liệu far chưa dùng để fine-tune ứng viên này.

Phiên notebook đầu tiên dừng trước huấn luyện vì Kaggle dùng Python 3.13, trong khi ONNX 1.17.0 không có wheel tương ứng. Bản sửa chọn ONNX 1.19.1, ONNX Runtime 1.23.2 và NumPy 2.2.6 trên Python 3.13; Python cũ hơn giữ các pin trước. Đã tải thành công cả sáu wheel Linux Python 3.13 để kiểm tra. Notebook chỉ cho phép wheel có sẵn và khóa torch/torchvision theo phiên bản CUDA do Kaggle cung cấp. Xuất ONNX vẫn dùng opset 12, `dynamo=False`, kiểm tra IR ≤10 và so sánh xác suất PT/ONNX trước khi tạo gói model. [Wheel ONNX](https://pypi.org/project/onnx/1.19.1/), [wheel ONNX Runtime](https://pypi.org/project/onnxruntime/1.23.2/), [wheel NumPy](https://pypi.org/project/numpy/2.2.6/).

## Theo dõi và tải kết quả

Chạy từ thư mục `DA2` trong PowerShell:

```powershell
& '.\.venv-cloud\Scripts\kaggle.exe' kernels status nguyntrnminhc/yawn-gpu-near-medium-20261011-033302
& '.\.venv-cloud\Scripts\kaggle.exe' kernels logs nguyntrnminhc/yawn-gpu-near-medium-20261011-033302
```

Theo dõi log trực tiếp trên Windows (tránh lỗi mã hóa tiếng Việt):

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& '.\.venv-cloud\Scripts\kaggle.exe' kernels logs nguyntrnminhc/yawn-gpu-near-medium-20261011-033302 --follow
```

Log có thể chưa được trả về trong lúc cấp máy/khởi động. Mở notebook để xem trạng thái trực tiếp. Không push lại chỉ vì log trống: mỗi push tạo một phiên mới và sử dụng hạn mức GPU.

Sau khi phiên hoàn thành:

```powershell
& '.\.venv-cloud\Scripts\python.exe' -X utf8 -m kaggle kernels output nguyntrnminhc/yawn-gpu-near-medium-20261011-033302 -p kaggle_output/yawn_near_medium --file-pattern 'yawn_kaggle_result\.zip$'
```

Giải nén `yawn_kaggle_result.zip` vào `models/`, kiểm tra báo cáo/parity và phát lại video giữ riêng trước khi chạy profile ứng viên. Xem [hướng dẫn dataset](kaggle_upload/README.md) và [notebook nguồn](notebooks/yawn_near_medium_kaggle.ipynb).

## MCP Kaggle trong Codex

MCP chính thức: `https://www.kaggle.com/mcp`. Đã thêm server `kaggle` vào cấu hình Codex tại máy; helper lấy credential riêng tại máy, không chứa token trong project/config. [Tài liệu Kaggle MCP](https://www.kaggle.com/docs/mcp), [cấu hình MCP Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

Hai việc khác nhau cần xác minh: khởi tạo MCP/lấy danh sách công cụ và gọi được công cụ đọc tài nguyên Private. HTTP 200 hoặc 71 công cụ không chứng minh đã có quyền truy cập Private.

Token mới đã xác minh ngày 11/10/2026: còn hiệu lực, thuộc `nguyntrnminhc`, đọc dataset Private và hạn mức GPU qua API/CLI thành công. MCP cũng trả lời bước `authorize` rằng đã xác thực, nhưng `get_dataset_info` trên cùng dataset Private vẫn bị từ chối quyền `datasets.get`. Vì vậy việc upload/chạy/theo dõi dùng API/CLI đã được cấp quyền; chưa coi MCP Private là hoàn tất. Không cần tạo thêm token khi API/CLI đã xác minh thành công.

Đăng nhập `codex.cmd mcp login kaggle` hiện bị Kaggle từ chối với `ClientId too small: codex`; đăng ký CIMD cũng không được server quảng bá. Phiên OAuth sẵn có dùng được với CLI, nhưng MCP từ chối đọc dataset/notebook Private bằng token đó. Đã giữ nguyên credential OAuth và dùng đường token do Kaggle hướng dẫn để hoàn thiện MCP.

1. Mở [Kaggle API settings](https://www.kaggle.com/settings/api), tạo/copy token theo mục Token Authentication của tài liệu MCP. Không gửi token vào chat.
2. Nhập token ẩn trong terminal của bạn:

```powershell
& '.\.venv-cloud\Scripts\python.exe' tools/save_kaggle_token.py
```

Token được lưu tại `~/.kaggle/access_token` theo cách Kaggle hướng dẫn. Đây là credential ở ngoài repository. Helper ưu tiên `KAGGLE_API_TOKEN`, rồi file token này, rồi OAuth hiện có. Không chạy `tools/kaggle_mcp_headers.py` để xem output: stdout của nó là kênh credential riêng cho Codex.

3. Kiểm tra quyền đọc Private:

```powershell
& '.\.venv-cloud\Scripts\python.exe' tools/check_kaggle_connection.py --dataset nguyntrnminhc/yawn-near-medium-20261011-033302
```

Chỉ coi MCP hoàn tất khi có `private_resource_authorized: true`. Khởi động lại/reload Codex để nạp server và token mới; cấu hình CLI tại máy không tự thêm công cụ vào một phiên ChatGPT đang chạy. Nếu token mới vẫn bị từ chối, tiếp tục dùng CLI đã xác thực và kiểm tra quyền token; không công khai dataset để né lỗi Private.

## Tạo phiên train mới

```powershell
& '.\.venv-cloud\Scripts\python.exe' tools/prepare_kaggle_training.py --username nguyntrnminhc
```

Công cụ chỉ tạo thư mục upload riêng, kiểm tra checksum ZIP, sao chép đúng dataset/notebook, đặt notebook Private và GPU. Nó không upload hoặc chạy job. Dùng đường dẫn **Windows tuyệt đối** của hai thư mục trả về với `kaggle datasets create -p ... --keep-tabular` và `kaggle kernels push -p ... --accelerator NvidiaTeslaT4 --timeout 3600`. Không truyền `--public`. Đợi dataset `ready` trước khi push notebook. Phiên có slug riêng để giữ các kết quả trước.

## Google Colab

[Colab MCP chính thức](https://github.com/googlecolab/colab-mcp) là một bridge chạy local tới Colab trong trình duyệt, yêu cầu client hỗ trợ cập nhật danh sách công cụ. Chưa cài/kết nối Colab trong phiên này. Notebook đang dùng các đường dẫn `/kaggle/input` và `/kaggle/working`; cần profile riêng nếu chuyển sang Colab. Kaggle là môi trường đã setup cho gói hiện tại.
