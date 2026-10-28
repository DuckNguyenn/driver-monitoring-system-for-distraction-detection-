# Miền giám sát tài xế

Thuật ngữ nghiệp vụ dùng chung của hệ thống. Hành vi và cách triển khai nằm trong tài liệu feature.

## Quan sát và nhận diện

**Observation**: Một quan sát trạng thái tài xế gắn với thời điểm nguồn và mức chất lượng quan sát.

**Chất lượng quan sát**: Mức độ đủ bằng chứng hình ảnh để đưa ra kết luận về mắt hoặc miệng.

**Mắt nhắm kéo dài**: Hai mắt cùng được xác nhận nhắm liên tục đủ thời gian quy định.
_Tránh_: Đồng nhất với một mắt nhắm hoặc một frame có xác suất cao.

**Eye cycle**: Một chu kỳ mở–nhắm–mở của một mắt; có thể là nháy riêng một mắt hoặc nhắm lâu.

**Blink**: Sự kiện chớp ngắn có chu kỳ của cả hai mắt được ghép theo thời gian.
_Tránh_: Dùng mọi eye cycle như một blink hai mắt.

**Yawn event**: Một đợt ngáp đã được xác nhận, chỉ tính một lần trong cùng đợt.
_Tránh_: Gọi mỗi frame miệng há là một lần ngáp.

**Nhánh mắt có kính**: Bộ nhận diện mắt chuyên biệt được chọn khi có đủ bằng chứng đeo kính.

## Quyết định và cảnh báo

**NORMAL**: Quan sát hợp lệ chưa đạt điều kiện cảnh báo.

**WARNING**: Có dấu hiệu cần chú ý nhưng chưa đạt điều kiện bật cảnh báo mức ALERT.

**ALERT**: Trạng thái đã đạt điều kiện cảnh báo theo logic giám sát tài xế.

**UNKNOWN**: Chưa đủ bằng chứng để kết luận một trạng thái quan sát.
_Tránh_: Gọi UNKNOWN là bình thường hoặc suy diễn xác suất thiếu thành số không.

**Đợt ALERT**: Một lần chuyển vào trạng thái ALERT, có danh tính riêng để tránh báo lặp khi kết nối lại.

**Cảnh báo tại chỗ**: Tín hiệu cảnh báo được phát gần tài xế bằng buzzer.

**Thông báo từ xa**: Thông tin cảnh báo được chuyển tới người theo dõi qua kết nối mạng.
_Tránh_: Đồng nhất với tín hiệu đảm bảo đã tới điện thoại hoặc đã được người nhận đọc.

## Phiên và bằng chứng

**Phiên camera**: Một lần theo dõi hình ảnh được lấy trực tiếp từ camera.

**Phiên phát lại**: Một lần xử lý video đã lưu, sử dụng thời gian của video.

**MonitorSnapshot**: Bản chụp dữ liệu quan sát và quyết định của một phiên tại một thời điểm.

**Tập kiểm thử độc lập**: Dữ liệu không dùng để huấn luyện, chọn checkpoint hoặc điều chỉnh ngưỡng.

**Bằng chứng phát triển**: Kết quả trên dữ liệu đã được dùng để sửa hoặc lựa chọn hệ thống.
_Tránh_: Trình bày như nghiệm thu trên người và điều kiện mới.
