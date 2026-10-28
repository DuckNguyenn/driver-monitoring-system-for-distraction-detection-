"""Generate diagrams of implemented LAN interfaces; no physical-device claims."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from draw_report_architectures import canvas, box, arrow, label, save, INK
from matplotlib.patches import Rectangle


def overall():
    fig, ax = canvas(8.7)
    box(ax, 1.45, 7.15, 2.45, 1., 'Camera / video\n640×480')
    box(ax, 5.75, 7.15, 4., 1., 'YuNet → ROI → chất lượng\nClassifier mắt và ngáp', 11)
    box(ax, 5.75, 5.45, 4., 1., 'Monitor theo thời gian\nNORMAL · WARNING\nALERT · UNKNOWN', 9.5)
    ax.add_patch(Rectangle((3.45, 4.72), 4.6, 3.3, fill=False, ec=INK, lw=1., ls='--'))
    label(ax, 5.75, 8.2, 'Tiến trình suy luận · PC / Radxa', 11)
    box(ax, 10.4, 7.15, 2.75, 1., 'ESP32 → Buzzer\nUSB serial · ACK', 10.5)
    box(ax, 10.4, 5.45, 2.75, 1., 'Nhật ký gốc\nJSONL · CSV', 10.5)
    arrow(ax, [(2.68, 7.15), (3.72, 7.15)])
    arrow(ax, [(5.75, 6.63), (5.75, 5.97)])
    arrow(ax, [(7.77, 5.45), (8.52, 5.45), (8.52, 7.15), (9.0, 7.15)])
    arrow(ax, [(7.77, 5.45), (9.0, 5.45)])
    box(ax, 1.45, 5.45, 2.6, 1., 'Khung hình Driver monitor\nVẽ một lần\nCửa sổ PC tùy chọn', 9.5)
    arrow(ax, [(3.73, 5.45), (2.77, 5.45)])
    box(ax, 1.45, 3.82, 2.6, .95, 'Luồng JPEG bất đồng bộ\nĐệm 1 ảnh · 15 FPS', 9.5)
    arrow(ax, [(1.45, 4.93), (1.45, 4.32)])
    box(ax, 5.75, 3.82, 4., .95, 'Queue snapshot / JPEG giới hạn\nGiữ mới nhất · không chờ client', 10.5)
    arrow(ax, [(2.77, 3.82), (3.73, 3.82)])
    arrow(ax, [(5.75, 4.93), (5.75, 4.32)])
    box(ax, 10.4, 3.82, 2.75, .95, 'Chỉ mục SQLite\nNhập lại không trùng', 10)
    arrow(ax, [(10.4, 4.93), (10.4, 4.32)])
    box(ax, 5.75, 2.16, 4., 1., 'FastAPI · tiến trình riêng\nREST + WebSocket · cổng 8765', 11)
    arrow(ax, [(5.75, 3.32), (5.75, 2.68)])
    arrow(ax, [(9.0, 3.82), (8.55, 3.82), (8.55, 2.16), (7.77, 2.16)])
    box(ax, 1.68, .75, 2.85, .95, 'React web\nTrình duyệt', 10.5)
    box(ax, 10.4, .75, 2.85, .95, 'App iPhone\nReact Native · Expo Go', 10.5)
    arrow(ax, [(3.73, 2.16), (1.68, 2.16), (1.68, 1.25)])
    arrow(ax, [(7.77, 2.16), (10.4, 2.16), (10.4, 1.25)])
    label(ax, 5.75, .7, 'Cùng Wi-Fi · chỉ giám sát\nMã kết nối bảo vệ dữ liệu và camera', 10)
    save(fig, 'dashboard_overall')


def clients():
    fig, ax = canvas(7.2)
    box(ax, 2.0, 6.2, 3.45, .9, 'PC / Radxa\nAPI + web đã build')
    box(ax, 6.25, 6.2, 3.3, .9, 'Trình duyệt web\nGiám sát · Lịch sử · Kết nối', 10)
    box(ax, 10.35, 6.2, 3.1, .9, 'iPhone / Expo Go\nApp đang mở', 10.5)
    arrow(ax, [(3.75, 6.2), (4.55, 6.2)])
    arrow(ax, [(3.75, 5.95), (4.05, 5.95), (4.05, 5.22), (10.35, 5.22), (10.35, 5.72)])
    box(ax, 6, 4.3, 10.9, 1.05, 'REST: Bearer token     |     WebSocket: thông điệp auth đầu tiên\nSnapshot có UTC + thời gian nguồn, xác suất thiếu giữ null', 11)
    box(ax, 2.2, 2.65, 3.5, 1.1, 'Khung hình Driver monitor\nJPEG mặc định 15 FPS\n≤640×480 · giữ mới nhất', 10.5)
    box(ax, 6.15, 2.65, 3.55, 1.1, 'Biểu đồ 60 giây · 3 hàng\nMắt 1 · Mắt 2 · Ngáp\nNhật ký phiên → CSV', 10.5)
    box(ax, 10.05, 2.65, 3.55, 1.1, 'App vào nền\nNgắt truyền ảnh và WS\nMở lại → đồng bộ', 10.5)
    for x in (2.2, 6.15, 10.05):
        arrow(ax, [(x, 3.75), (x, 3.23)])
    box(ax, 6, .85, 10.9, .9, 'Không có dữ liệu mới >2 giây: làm mờ dữ liệu cũ, kết nối lại\nALERT camera mới: banner và rung một lần; phát lại video được ghi rõ', 11)
    save(fig, 'dashboard_connections')


if __name__ == '__main__':
    overall(); clients()
