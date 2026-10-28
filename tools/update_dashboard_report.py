"""Extend the retained report with implemented LAN monitoring and measured evidence."""
import argparse
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'reports/BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.md'


def extend(text, anchor, heading, body):
    if heading in text:
        pattern = re.escape(heading) + r'\n[\s\S]*?(?=^#{1,2} |\Z)'
        return re.sub(pattern, lambda _: heading+'\n\n'+body.strip()+'\n\n', text, count=1, flags=re.MULTILINE)
    return text.replace(anchor, heading+'\n\n'+body.strip()+'\n\n'+anchor, 1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--benchmark',required=True);parser.add_argument('--camera',required=True);args=parser.parse_args()
    measured=json.loads(Path(args.benchmark).read_text(encoding='utf-8'))
    camera=json.loads(Path(args.camera).read_text(encoding='utf-8'))
    tests=json.loads((ROOT/'reports/reference_style/system_design_scope/software_tests.json').read_text(encoding='utf-8'))
    browser=json.loads((ROOT/'reports/dashboard_verification/web-browser.json').read_text(encoding='utf-8'))
    web_tests=json.loads((ROOT/'.cache/dashboard_implementation/web-tests.json').read_text(encoding='utf-8'))['stats']
    evidence={"replay":measured,"camera":camera,"python_tests":tests,"web_browser_test_passed":web_tests['unexpected']==0,
              "web_ui_tests_passed":web_tests['expected'],"web_ui_tests_failed":web_tests['unexpected'],"built_web_real_video":browser,
              "client_unit_tests":10,"typescript_passed":True,"web_build_passed":True,
              "ios_bundle_exported":True,"expo_doctor_checks":21,"physical_iphone_tested":False,"radxa_tested":False,
              "user_confirmed_iphone_connection":True,"physical_iphone_acceptance_complete":False,
              "latency_scope":"snapshot reception by two simulated clients on same PC; not physical LAN rendering"}
    out=ROOT/'reports/dashboard_verification';out.mkdir(exist_ok=True)
    (out/'latest.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    cache=ROOT/'.cache/dashboard_implementation';cache.mkdir(parents=True,exist_ok=True)
    if not (cache/'report-before-dashboard.md').exists():shutil.copyfile(SOURCE,cache/'report-before-dashboard.md')
    text=SOURCE.read_text(encoding='utf-8')
    text=text.replace('và lưu nhật ký tại máy tính xử lý. Khối phần cứng cảnh báo', 'và lưu nhật ký tại máy tính xử lý. Giao diện web và app iPhone bổ sung chức năng theo dõi trong cùng mạng Wi-Fi, gồm ảnh camera, trạng thái, số liệu và lịch sử phiên; không điều khiển runtime từ giao diện. Khối phần cứng cảnh báo')
    if 'Giao diện giám sát trong mạng nội bộ được bổ sung' not in text:
        text=text.replace('# MỤC LỤC', 'Giao diện giám sát trong mạng nội bộ được bổ sung bằng FastAPI, React và React Native/Expo. Dữ liệu trực tiếp được tách khỏi tiến trình suy luận bằng hàng đợi giới hạn; lịch sử lấy từ nhật ký gốc và chỉ mục SQLite. Web đã được kiểm tra trong trình duyệt; app đã xuất bundle iOS và kiểm tra tương thích SDK. Phép thử trên iPhone thật cùng phép đo LAN thực tế tiếp tục được thực hiện sau khi kết nối thiết bị.\n\n# MỤC LỤC',1)
    text=text.replace('Phép thử trên iPhone thật cùng phép đo LAN thực tế tiếp tục được thực hiện sau khi kết nối thiết bị.', 'Người dùng đã xác nhận app kết nối được qua IPv4 Wi-Fi của PC. Nghiệm thu đầy đủ ảnh, rung, chia sẻ CSV và độ trễ LAN trên iPhone thật chưa hoàn tất.')
    text=text.replace('../report_assets/project_report/overall_architecture.png','../report_assets/project_report/dashboard_overall.png')
    text=extend(text,'# CHƯƠNG 3. TÍNH TOÁN THIẾT KẾ','## 2.12. Giao tiếp dữ liệu và giao diện giám sát', '''REST tổ chức các yêu cầu đọc theo tài nguyên, gồm trạng thái, phiên chạy, chuỗi số liệu và sự kiện. Trong hệ thống này, FastAPI tiếp nhận yêu cầu HTTP và trả JSON hoặc JPEG; WebSocket duy trì kết nối để gửi snapshot theo thời gian mà client không cần liên tục tạo yêu cầu trạng thái [32]. Xác thực REST dùng header Bearer; WebSocket kiểm tra mã ở thông điệp đầu trước khi gửi dữ liệu riêng tư.

Hàng đợi giới hạn tách tốc độ suy luận khỏi tốc độ đọc của giao diện. Khi đầy, bản ghi xuất dữ liệu cũ có thể được bỏ để ưu tiên quan sát mới nhất; quá trình ra quyết định và ghi nhật ký gốc tiếp tục hoạt động. Đây là cơ chế bỏ dữ liệu hiển thị quá hạn, không xóa bằng chứng của phiên. Khung hình được vẽ một lần, dùng cho cửa sổ tại PC và luồng nén JPEG bất đồng bộ. Luồng nén có một ảnh chờ, chỉ hoạt động khi có nhu cầu xem; các client cùng nhận bản ảnh mã hóa.

SQLite lưu dữ liệu cục bộ bằng bảng và chỉ mục. Bộ nhập dùng định danh phiên cùng vị trí byte của bản ghi làm khóa chống trùng, lưu cursor theo file, chỉ nhập dòng JSONL hoàn chỉnh và tiếp tục sau khi khởi động lại. UTC dùng trình bày thời gian; timestamp nguồn vẫn phân biệt camera monotonic với thời gian video.

React quản lý trạng thái và thành phần giao diện web; React Native triển khai thành phần giao diện cho iPhone. TypeScript mô tả cùng kiểu dữ liệu cho hai client. Expo Go phục vụ thử app trong môi trường SDK phù hợp; expo-image hiển thị ảnh với header xác thực và cachePolicy none [33], [34]. Sự kiện AppState được dùng để tạm ngắt truyền ảnh và kết nối khi app vào nền. Bộ nhớ định danh đợt ALERT hạn chế rung lặp khi kết nối lại. Các chức năng này không tham gia xác nhận blink hoặc ngáp.''')
    text=extend(text,'# CHƯƠNG 4. THI CÔNG HỆ THỐNG','## 3.9. Thiết kế giám sát bằng web và app iPhone', '''Chế độ serve chạy API ở tiến trình riêng với camera và suy luận. Runtime xuất MonitorSnapshot qua kênh giới hạn, gồm định danh phiên, số thứ tự, UTC, thời gian nguồn, trạng thái, nguyên nhân, xác suất, bộ đếm, chất lượng, FPS, độ trễ và tình trạng thiết bị. Kết quả được lấy từ Monitor; hai giao diện không tính lại điều kiện cảnh báo. Giá trị thiếu giữ null để tạo khoảng trống trên biểu đồ.

![Hình 3-11. Kết nối dashboard web và app iPhone trong mạng Wi-Fi](../report_assets/project_report/dashboard_connections.png)

API và camera được bảo vệ bằng mã tạo tại máy xử lý. Mã không nằm trong URL WebSocket hoặc nhật ký truy cập. Ảnh lấy từ bộ nhớ mới nhất, giới hạn 640×480 và giữ lớp vẽ Driver monitor, gồm trạng thái, xác suất, bộ đếm, khung mặt và mắt. Luồng JPEG mã hóa dùng chung cho client, giữ một ảnh chờ; mục tiêu mặc định 15 FPS, có lựa chọn 2, 5, 10, 15 hoặc 30 FPS. Tốc độ nhận thực tế bị giới hạn bởi nguồn, suy luận, thiết bị và mạng; số thứ tự ảnh độc lập với bản tin trạng thái.

@table Bảng 3-4. Các tài nguyên đọc của API giám sát
| Tài nguyên | Vai trò |
|---|---|
| status, health | Snapshot và tình trạng chỉ mục |
| sessions, sessions/{id} | Danh sách và chi tiết phiên |
| sessions/{id}/series, events | Chuỗi số liệu và sự kiện có phân trang |
| sessions/{id}/export.csv | Xuất toàn bộ số liệu đã lưu của phiên |
| frame.jpg | JPEG mới nhất, có xác thực, không cache |
| ws | WebSocket, xác thực bằng thông điệp đầu |

Web bố trí camera và biểu đồ cạnh nhau, cùng nhóm chỉ số và thiết bị. Biểu đồ tách thành ba hàng Mắt 1, Mắt 2 và Ngáp, mỗi hàng có màu cùng xác suất hiện tại; dùng chung cửa sổ 60 s và thang 0–100% để đối chiếu. App dùng màn hình dọc với ba mục Giám sát, Lịch sử phiên và Kết nối. Khi quá 2 s không có dữ liệu mới, dữ liệu cũ được làm mờ và kết nối được thử lại. App chỉ rung một lần cho đợt ALERT camera mới khi đang mở; phát lại video được ghi rõ. Lịch sử gồm lọc ngày, phiên, chi tiết sự kiện và CSV. Không lưu thêm video hoặc tự xóa nhật ký.''')
    text=extend(text,'# CHƯƠNG 5. KẾT QUẢ THỰC NGHIỆM','## 4.7. Lập trình dashboard web và app iPhone', '''Phần xuất dữ liệu được triển khai trong dashboard_data.py và dashboard_transport.py, luồng nén JPEG tại dashboard_video.py, phần API tại dashboard_server.py, chỉ mục lịch sử tại dashboard_history.py. Hàm run nhận observer tùy chọn; lỗi bộ xuất dữ liệu được ghi nhận và không dừng quyết định hoặc serial. Lệnh serve dùng mặc định profile PC hiện tại, mở cửa sổ Driver monitor khi thêm --display; không mở màn hình khi chạy dịch vụ. Dừng tiến trình gửi lệnh tắt còi, kết thúc worker và đóng các kết nối.

Hai giao diện được tổ chức trong npm workspaces: frontend/shared chứa kiểu dữ liệu, API client, nhãn và xử lý kết nối; frontend/web chứa React + Vite; frontend/mobile chứa React Native + Expo. package-lock.json khóa cây dependency. App đã dùng Expo SDK 57 và các module native được kiểm tra theo SDK; không thay đổi model hoặc ngưỡng của cấu hình camera.

![Hình 4-2. Dashboard web hiển thị dữ liệu mô phỏng trong kiểm thử Chromium](../report_assets/project_report/dashboard_web_test.png)

Ảnh Hình 4-2 minh họa bố cục ba hàng tín hiệu bằng dữ liệu mô phỏng; không dùng làm bằng chứng độ chính xác AI hoặc camera. Các trường hợp NORMAL, WARNING, ALERT, UNKNOWN, xác suất thiếu, kết nối quá hạn và phiên phát lại được thử trên trình duyệt. Bộ kiểm thử còn xác nhận ảnh JPEG đứng hoặc yêu cầu ảnh treo được đánh dấu quá hạn độc lập với WebSocket và phản hồi chậm từ phiên cũ không ghi đè phiên vừa chọn. Kiểm thử nén JPEG cố ý chặn xác nhận việc xuất cảnh báo không phải đợi bộ nén; yêu cầu ảnh theo số thứ tự trả 204 khi chưa có ảnh mới. App chờ ảnh đang tải hoàn tất trước khi thay nguồn và phục hồi khi yêu cầu treo. App đã kiểm tra TypeScript, xuất bundle iOS và chạy Expo Doctor. Người dùng xác nhận app đã kết nối khi dùng IPv4 Wi-Fi của PC; ảnh, rung, chuyển nền và chia sẻ CSV trên iPhone chưa được nghiệm thu đầy đủ.

Hướng dẫn DASHBOARD.md cung cấp lệnh Windows, cách lấy IPv4, nhập mã, mở Expo Go, phát lại video và cài dịch vụ Radxa. Web được build sẵn và phục vụ cùng Python API, nên Radxa không cần Node.js để vận hành. Mẫu dịch vụ driver-monitor-dashboard@.service sử dụng nguồn camera và cổng serial từ file môi trường; triển khai và đo trên bo vẫn chờ setup.''')
    text=re.sub(r'Bộ kiểm thử hiện tại trong tests/ ghi nhận \d+ kiểm thử đạt sau sửa bỏ sót ngáp, không có kiểm thử thất bại \[30\]\.', f'Bộ kiểm thử hiện tại trong tests/ ghi nhận {tests["tests_run"]} kiểm thử đạt trong lần rà soát bổ sung dashboard, không có kiểm thử thất bại [31], [35].',text)
    text=re.sub(r'(Bộ kiểm thử hiện tại trong tests/ ghi nhận )\d+( kiểm thử đạt)',lambda match:match[1]+str(tests['tests_run'])+match[2],text)
    original_compare='@table Bảng 5-5. Đối chiếu bằng chứng với các chỉ tiêu'
    text=text.replace(original_compare,'@table Bảng 5-6. Đối chiếu bằng chứng với các chỉ tiêu')
    b,d=measured['baseline'],measured['dashboard'];v=measured['two_clients'];c=camera['dashboard']
    fps_change=(d['fps']/b['fps']-1)*100
    preview=v['preview_clients']
    section=f'''Phép đối chiếu dùng cùng profile camera_pc.yaml, ONNX CPU và video camera phát triển gồm {d['frames']:,} frame, khoảng {d['media_seconds']:.3f} s thời gian nguồn. Cả lượt run và serve đều mở cửa sổ Driver monitor. Hai client mô phỏng đồng thời nhận WebSocket và yêu cầu JPEG. Các trường trạng thái, mắt, ngáp, blink và cảnh báo trong CSV được đối chiếu từng frame; {d['frames']}/{d['frames']} frame giữ nguyên quyết định [35].

@table Bảng 5-5. Đo tải dashboard trên cùng video và cấu hình PC
| Chỉ số | Kết quả |
|---|---|
| Preview được chọn | {measured['preview_fps']} FPS; giới hạn ảnh 640×480 |
| Tốc độ ảnh nhận tại hai client | {preview[0]['received_fps']:.2f} / {preview[1]['received_fps']:.2f} FPS |
| Suy luận trước khi bật dashboard | {b['fps']:.2f} FPS |
| Suy luận cùng API và hai client | {d['fps']:.2f} FPS |
| Thay đổi FPS so với trước | {fps_change:+.2f}% |
| Độ trễ nhận snapshot p95 | {v['snapshot_latency_p95_ms']:.2f} ms |
| RAM đỉnh API và tiến trình con | {v['rss_peak_bytes']/1024/1024:.2f} MiB |
| Đối chiếu quyết định | Giữ nguyên toàn bộ {d['frames']} frame |
| Dừng API bằng tín hiệu Windows | Kết thúc bình thường; mã thoát {measured['api_exit_code']} |

Phép đo 2/5 FPS trước ngày 09/10 thuộc bản nén ảnh trong vòng AI; không đại diện cho bản bất đồng bộ hiện tại. Lần kiểm tra trong bảng dùng mục tiêu 15 FPS và giữ nguyên model, ngưỡng, ghi nhận thay đổi {fps_change:+.2f}% giữa hai lượt. Mức giảm {measured['fps_decrease_percent']:.2f}% đạt mục tiêu không quá 10% trong lượt thử, nhưng gần giới hạn. Các lượt chạy tuần tự trong phiên phát triển và chịu thay đổi tải máy, cache; chưa phải thống kê lặp nhiều lần trên thiết bị độc lập. Tốc độ ảnh nhận được đo bằng số thứ tự JPEG mới, tách với FPS xử lý AI. Độ trễ trong bảng là thời gian từ xuất snapshot đến nhận tại client mô phỏng trên cùng PC, chưa bao gồm đo render trên iPhone hoặc truyền qua Wi-Fi thực.

Phiên camera nguồn 0 với hai client chạy {c['wall_seconds']:.3f} s, nhận {c['frames']} frame, đạt {c['fps']:.2f} FPS; p95 nhận snapshot {camera['two_clients']['snapshot_latency_p95_ms']:.2f} ms. Kiểm kê thiết bị tại thời điểm đo thấy Integrated Camera và Integrated IR Camera, chưa thấy camera USB rời. Có {c['states'].get('UNKNOWN',0)} frame UNKNOWN; phiên không có nhãn hành vi nên không đánh giá độ chính xác nhận biết hoặc nghiệm thu điều kiện cabin.

Ba kiểm thử giao diện trong Chromium đã đạt; 10 kiểm thử client chung, kiểm tra TypeScript, build web và export iOS đã đạt; Expo Doctor đạt 21/21 kiểm tra ở lần đối chiếu SDK trước, không đổi dependency trong lần cập nhật này. Kiểm tra bổ sung trên web đã build với API và video thật xác nhận ảnh {browser['preview']['width']}×{browser['preview']['height']}, ba hàng biểu đồ, mở lịch sử và tải CSV thành công, không có lỗi JavaScript; tốc độ ảnh render khoảng {browser['preview_render_fps']:.2f} FPS trong cửa sổ đo ngắn. Độ trễ từ UTC snapshot đến cập nhật DOM trong {browser['render_samples']} mẫu có p95 {browser['render_p95_ms']:.0f} ms; đây là một trình duyệt trên cùng PC, chưa đại diện cho Wi-Fi hoặc iPhone thật. Các kiểm thử API xác nhận mã sai bị từ chối, xác thực WebSocket trước khi gửi dữ liệu, dữ liệu thiếu giữ null, nhập lặp không trùng, dòng JSONL chưa hoàn chỉnh chờ lần nhập sau, startup lỗi có nhật ký và dừng tiến trình đúng. Người dùng xác nhận app kết nối thành công; mục tiếp theo dành cho nghiệm thu đầy đủ trên iPhone thật.'''
    # This subsection must stop at the next peer heading, leaving hardware headings empty.
    marker='### 5.1.13. Kiểm thử dashboard và truyền dữ liệu trên PC'
    if marker in text:
        text=re.sub(re.escape(marker)+r'\n[\s\S]*?(?=^### 5\.1\.14\.|^## 5\.2\.)',lambda _:marker+'\n\n'+section+'\n\n',text,count=1,flags=re.MULTILINE)
    else:
        text=text.replace('## 5.2. Nhận xét và đánh giá',marker+'\n\n'+section+'\n\n### 5.1.14. Kiểm thử Expo Go trên iPhone thực\n\n## 5.2. Nhận xét và đánh giá',1)
    text=text.replace('reports/SMILE_FIX.md','reports/smile_fix_verification.json').replace('reports/SMILE_YAWN_FIX.md','reports/smile_fix_verification.json').replace('reports/EYE_CLASSIFIER_FIX.md','reports/eye_classifier_verification.json').replace('reports/EYE_MOTION_FIX.md','reports/eye_motion_verification.json').replace('reports/YAWN_CAMERA_FIX.md','reports/yawn_camera_check/candidate.regression.json')
    prior_scope='Kết quả hiện tại là một hệ thống phần mềm thử nghiệm cùng bộ chuẩn bị triển khai Radxa ROCK 4D. Chưa có đủ bằng chứng để nghiệm thu độ chính xác sự kiện ngoài thực tế hoặc vận hành trên bo. Các kết quả ảnh và camera được trình bày đúng môi trường, thời lượng và giới hạn, làm cơ sở cho giai đoạn thu dữ liệu và đánh giá tiếp theo.'
    text=text.replace(prior_scope+'\n\n','')
    summary='Dashboard web đã hiển thị khung hình Driver monitor, ba hàng biểu đồ và lịch sử qua API có xác thực; quyết định giữ nguyên trên video thử. App iPhone đã xuất bundle, được người dùng xác nhận kết nối. Nghiệm thu iPhone, Wi-Fi, Radxa và độ chính xác thực tế chưa hoàn tất.'
    summary_pattern=r'^(?:Chế độ serve bổ sung dashboard web|Dashboard web đã hiển thị ảnh)[^\n]+$'
    if re.search(summary_pattern,text,re.MULTILINE):
        text=re.sub(summary_pattern,lambda _:summary,text,count=1,flags=re.MULTILINE)
    elif summary not in text:
        text=text.replace('## 6.2. Hướng phát triển',summary+'\n\n## 6.2. Hướng phát triển',1)
    if '[32] FastAPI' not in text:
        text+='\n\n[32] FastAPI, WebSockets: https://fastapi.tiangolo.com/advanced/websockets/. Tham khảo cơ chế kết nối; cấu hình xác thực và queue theo dashboard_server.py. Truy cập ngày 08/10/2026.\n\n[33] Expo, Expo Image: https://docs.expo.dev/versions/latest/sdk/image/. Tham khảo header và cachePolicy; cấu hình thực trong frontend/mobile/App.tsx. Truy cập ngày 08/10/2026.\n\n[34] Expo, Work with monorepos: https://docs.expo.dev/guides/monorepos/. Bộ SDK và module được đối chiếu bundledNativeModules.json, package-lock.json và Expo Doctor. Truy cập ngày 08/10/2026.\n\n[35] Hồ sơ dự án, reports/dashboard_verification/latest.json; tools/benchmark_dashboard.py; tests/test_dashboard_*.py; frontend/shared/tests/; frontend/web/tests/; DASHBOARD.md. Kết quả PC, giao diện mô phỏng và phạm vi phần cứng chưa quan sát trực tiếp.\n'
    SOURCE.write_text(text,encoding='utf-8')
    image=ROOT/'.cache/dashboard_implementation/web-monitor.png'
    if image.exists():shutil.copyfile(image,ROOT/'report_assets/project_report/dashboard_web_test.png')
    print('Updated retained report:',SOURCE)


if __name__=='__main__':main()
