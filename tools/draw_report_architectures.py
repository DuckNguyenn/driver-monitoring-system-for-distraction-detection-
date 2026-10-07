"""Evidence-grounded architecture figures for the Vietnamese project report."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'report_assets/project_report'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Ellipse

INK = '#263746'
FILL = '#f1f4f6'


def canvas(height=7):
    fig, ax = plt.subplots(figsize=(8.5, height*.85))
    ax.set(xlim=(0, 12), ylim=(0, height))
    ax.axis('off')
    fig.subplots_adjust(left=.015, right=.985, top=.98, bottom=.02)
    return fig, ax


def box(ax, x, y, w, h, text, size=11, dashed=False, fill=FILL):
    ax.add_patch(FancyBboxPatch((x-w/2, y-h/2), w, h,
        boxstyle='round,pad=0.025,rounding_size=.09',
        edgecolor=INK, facecolor=fill, linewidth=1.1,
        linestyle='--' if dashed else '-'))
    ax.text(x, y, text, ha='center', va='center', fontsize=size,
            fontfamily='DejaVu Sans', color=INK, linespacing=1.45)


def arrow(ax, points, dashed=False):
    style = '--' if dashed else '-'
    if len(points)>2:
        ax.plot(*zip(*points[:-1]), color=INK, lw=1.1, ls=style)
    ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle='-|>',
        mutation_scale=13, linewidth=1.1, color=INK, linestyle=style))


def label(ax, x, y, text, size=10):
    ax.text(x, y, text, ha='center', va='center', fontsize=size,
            fontfamily='DejaVu Sans', color=INK, linespacing=1.4,
            bbox={'facecolor':'white','edgecolor':'none','pad':1})


def save(fig, stem):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / (stem+'.png'), dpi=260, facecolor='white')
    fig.savefig(OUT / (stem+'.svg'), facecolor='white')
    plt.close(fig)


def overall():
    fig, ax = canvas(8.2)
    box(ax,1.45,6.6,2.5,1.1,'Camera\n640×480')
    box(ax,1.45,4.7,2.5,1.1,'Video có sẵn\nTimestamp ghi ảnh')
    ax.add_patch(Rectangle((3.35,3.05),5.3,4.65,fill=False,ec=INK,lw=1.2))
    label(ax,6,7.35,'Máy tính xử lý: PC / Radxa',12)
    box(ax,6,6.25,4.6,1.1,'YuNet → ROI → chất lượng\nClassifier mắt và ngáp')
    box(ax,6,4.55,4.6,1.05,'Monitor theo thời gian\nNORMAL · WARNING · ALERT · UNKNOWN',10)
    label(ax,6,3.5,'PC: ONNX CPU — đã thử nghiệm\nRadxa: RKNN NPU — chưa chạy trên bo',10)
    arrow(ax,[(2.72,6.6),(3.1,6.6),(3.1,6.25),(3.67,6.25)])
    arrow(ax,[(2.72,4.7),(3.1,4.7),(3.1,5.75),(3.67,5.75)])
    arrow(ax,[(6,5.68),(6,5.1)])
    box(ax,10.55,7.1,2.5,.95,'Hiển thị\nTùy chọn')
    box(ax,10.55,5.6,2.5,.95,'Nhật ký\nJSONL · CSV · JSON',10)
    box(ax,10.55,4.1,2.5,.95,'ESP32\nNhận lệnh serial')
    box(ax,10.55,2.25,2.5,.95,'Buzzer active\nCảnh báo tại chỗ')
    for y in (7.1,5.6,4.1):
        arrow(ax,[(8.33,4.55),(8.95,4.55),(8.95,y),(9.27,y)])
    arrow(ax,[(10.55,3.6),(10.55,2.75)])
    label(ax,11.25,3.18,'GPIO25',9.5)
    label(ax,6,2.5,'PC/Radxa → USB serial 115200 baud → ESP32\nESP32 → tín hiệu điều khiển → buzzer',11)
    label(ax,6,.9,'Sơ đồ thiết kế theo runtime và firmware hiện có.\nKết quả trên PC và phần kiểm thử phần cứng được báo riêng.',10)
    save(fig,'overall_architecture')


def hardware():
    fig, ax = canvas(6.4)
    box(ax,1.5,4.9,2.65,1.35,'PC / Radxa\nUSB host')
    box(ax,5.9,4.9,3.1,1.35,'ESP32\nUSB serial\nGPIO25 · GND')
    box(ax,10.15,4.9,3.0,1.35,'Module còi active\nCó driver\nIN · VCC · GND')
    arrow(ax,[(2.85,5.2),(4.32,5.2)])
    label(ax,3.6,5.72,'ALERT 1 / ALERT 0',9.5)
    arrow(ax,[(4.32,4.65),(2.85,4.65)])
    label(ax,3.6,4.05,'ACK: OK ALERT …',9.5)
    arrow(ax,[(7.48,5.15),(8.62,5.15)])
    label(ax,8.05,5.75,'GPIO25 → IN',9.5)
    ax.plot([7.48,8.62],[4.55,4.55],color=INK,lw=1.1)
    label(ax,8.05,3.98,'GND chung',9.5)
    box(ax,10.15,2.8,3.0,.9,'Nguồn cấp module\nTheo điện áp định mức',10)
    arrow(ax,[(10.15,3.27),(10.15,4.19)])
    box(ax,4.05,2.45,6.6,1.15,'Host gửi lại trạng thái mỗi 0,5 s\nESP32 tắt còi nếu mất lệnh hợp lệ ≥2 s',11)
    label(ax,6,.7,'USB đồng thời cấp nguồn ESP32. GPIO25 chỉ điều khiển đầu vào driver.\nSơ đồ kết nối theo mã nguồn; chưa xác nhận trên thiết bị thực.',10)
    save(fig,'esp32_buzzer_architecture')


def roi():
    fig, ax = canvas(7)
    ax.add_patch(Rectangle((.3,1.2),4.1,5.25,fc='#fafafa',ec=INK,lw=1.2))
    label(ax,2.35,6.72,'Ảnh gốc và ROI (minh họa)',11)
    ax.add_patch(Ellipse((2.35,3.85),2.45,3.7,fc='#f1f4f6',ec='#8a949c',lw=1))
    ax.add_patch(Rectangle((1.1,2),2.5,3.7,fill=False,ec=INK,lw=1.2))
    ax.add_patch(Rectangle((.85,1.63),3.0,4.44,fill=False,ec=INK,lw=1,ls='--'))
    for x in [1.65,3.05]:
        ax.plot(x,4.5,'o',color=INK,markersize=3)
        ax.add_patch(Rectangle((x-.56,4.08),1.12,.84,fill=False,ec='#496c85',lw=1.5))
    ax.annotate('',xy=(3.05,5.35),xytext=(1.65,5.35),
                arrowprops={'arrowstyle':'<->','color':INK,'lw':1})
    label(ax,2.35,5.57,'d',11)
    label(ax,2.35,.68,'Mỗi mắt: 0,8d × 0,6d\nMặt: mở rộng 10% mỗi phía',10.5)
    box(ax,6.6,5.25,3.35,1.1,'Hai ROI mắt\nRGB · 224×224')
    box(ax,6.6,2.75,3.35,1.1,'ROI mặt mở rộng\nRGB · 224×224')
    arrow(ax,[(3.62,4.5),(4.65,4.5),(4.65,5.25),(4.89,5.25)])
    arrow(ax,[(3.88,3.1),(4.65,3.1),(4.65,2.75),(4.89,2.75)])
    box(ax,10.2,5.25,3.05,1.5,'Classifier mắt\nChung trọng số\nSuy luận từng ROI',10.5)
    box(ax,10.2,2.75,3.05,1.5,'Classifier ngáp\nĐầu vào vùng mặt',10.5)
    arrow(ax,[(8.31,5.25),(8.63,5.25)])
    arrow(ax,[(8.31,2.75),(8.63,2.75)])
    label(ax,8.1,1.05,'YuNet tìm mặt trên ảnh thu nhỏ; ROI lấy từ ảnh gốc.\nKiểm tra chất lượng trước khi dùng xác suất cho quyết định.',10)
    save(fig,'roi_classifier_architecture')


def radxa():
    fig, ax = canvas(7.6)
    label(ax,6,7.3,'Kiến trúc triển khai dự kiến trên ROCK 4D',12)
    ax.add_patch(Rectangle((.35,2.35),5.3,4.45,fc='#fafafa',ec=INK,lw=1.1))
    ax.add_patch(Rectangle((6.15,2.35),5.5,4.45,fc='#fafafa',ec=INK,lw=1.1,ls='--'))
    label(ax,3,6.55,'CPU · Python / OpenCV',11)
    label(ax,8.9,6.55,'NPU RK3576 · RKNN Lite2',11)
    box(ax,3,5.4,4.45,1.05,'Camera → YuNet → ROI\nChất lượng + timestamp',10.5)
    box(ax,8.9,5.4,4.7,1.05,'Hai ROI mắt\nClassifier mắt .rknn',10.5,dashed=True)
    box(ax,8.9,3.8,4.7,1.05,'ROI mặt\nClassifier ngáp .rknn',10.5,dashed=True)
    box(ax,3,3.65,4.45,1.05,'Monitor theo thời gian\nSerial · nhật ký · hiển thị',10.5)
    arrow(ax,[(5.25,5.6),(6.5,5.6)])
    arrow(ax,[(5.25,5.15),(5.92,5.15),(5.92,3.8),(6.5,3.8)])
    arrow(ax,[(8.9,4.85),(8.9,4.56),(5.88,4.56),(5.88,3.95),(5.25,3.95)])
    arrow(ax,[(8.9,3.25),(8.9,2.85),(5.88,2.85),(5.88,3.4),(5.25,3.4)])
    box(ax,6,1.35,10.5,1.25,'Linux x86_64: .pt → ONNX → RKNN Toolkit2 (rk3576)\nManifest: nhãn + preprocessing + artifact + SHA256\nBlob nền đã tạo; model hiệu chỉnh cần chuyển lại và kiểm tra trên bo.',10.5)
    save(fig,'radxa_deployment_architecture')


def eye_confirmation():
    fig, ax = canvas(8.1)
    box(ax,6,7.15,10.6,1.05,'Hai ROI mắt → cùng classifier\nClosed/Open theo từng mắt; confidence ≥0,80',12)
    for x in (2,6,10):
        arrow(ax,[(6,6.6),(6,6.15),(x,6.15),(x,5.95)])
    box(ax,2,5.35,3.35,1.15,'Hai mắt Open\nP(Open) ≥0,80',11.5)
    box(ax,6,5.35,3.35,1.15,'Hai mắt Closed\nP(Closed) ≥0,80',11.5)
    box(ax,10,5.35,3.35,1.15,'Một mắt hoặc chưa rõ\nKhông xác nhận\nhai mắt nhắm',10.5)
    box(ax,2,3.7,3.35,1.15,'Mở ổn định 0,10 s\nChuẩn bị / hoàn tất\nchu kỳ mắt',11)
    box(ax,6,3.7,3.35,1.15,'Đo thời gian nhắm\nCác frame liên tục\nvà hợp lệ',11)
    box(ax,10,3.7,3.35,1.15,'Theo dõi riêng từng mắt\nNháy một mắt chỉ là\nchu kỳ chẩn đoán',10.5)
    for x in (2,6,10):
        arrow(ax,[(x,4.75),(x,4.3)])
    box(ax,3.5,1.9,5.4,1.05,'Hai khoảng nhắm chồng lấp\n0,05–0,5 s + mở lại → một blink',11)
    box(ax,9.1,1.9,4.4,1.05,'Hai mắt nhắm ≥1,5 s\n→ ALERT → bật buzzer',11)
    arrow(ax,[(2,3.1),(2,2.45)])
    arrow(ax,[(6,3.1),(6,2.8),(5.6,2.8),(5.6,2.45)])
    arrow(ax,[(6,3.1),(6,2.8),(9.1,2.8),(9.1,2.45)])
    label(ax,6,.65,'Mờ, mắt chưa rõ, đầu chuyển động hoặc gap >250 ms:\nngắt xác nhận nhắm kéo dài; không cộng thời gian thiếu dữ liệu.',11)
    save(fig,'eye_confirmation_design')


def yawn_confirmation():
    fig, ax = canvas(8.0)
    box(ax,6,7.15,10.6,1.0,'P(yawn) thô + timestamp → EMA theo thời gian (τ = 0,20 s)',11.5)
    box(ax,2,5.35,3.4,1.25,'Chưa xác nhận ngáp\nP <0,70:\nkhông tạo sự kiện',11)
    box(ax,6,5.35,3.4,1.25,'Ứng viên\nP ≥0,70 liên tục\nít nhất 1 giây',11)
    box(ax,10,5.35,3.4,1.25,'Đã xác nhận\nBộ đếm tăng một lần\nGiữ trạng thái đợt',11)
    arrow(ax,[(6,6.63),(6,6.0)])
    arrow(ax,[(3.74,5.35),(4.25,5.35)])
    arrow(ax,[(7.74,5.35),(8.25,5.35)])
    label(ax,6,4.35,'P giảm dưới 0,70 trước 1 s: hủy ứng viên',10.5)
    box(ax,10,3.05,3.4,1.15,'Kết thúc đợt\nP ≤0,35 liên tục\nít nhất 0,5 giây',11)
    box(ax,5.55,3.05,4.05,1.15,'Sẵn sàng đợt tiếp theo\nKhông đếm lặp khi\ngiữ miệng đang ngáp',11)
    arrow(ax,[(10,4.7),(10,3.65)])
    arrow(ax,[(8.25,3.05),(7.6,3.05)])
    arrow(ax,[(3.5,3.05),(2,3.05),(2,4.7)])
    box(ax,6,1.2,10.6,1.0,'Cửa sổ 60 s: ≥2 đợt → bằng chứng ngáp thường xuyên\nMột đợt ngáp chỉ ghi nhận; bật buzzer cần điều kiện cảnh báo tổng hợp',11)
    save(fig,'yawn_confirmation_design')


def decision_design():
    fig, ax = canvas(9.2)
    box(ax,4.3,8.25,7.4,1.25,'Thời gian / độ mới / chất lượng hợp lệ?\nPhân phối xác suất hợp lệ; mắt đủ chắc chắn?',11.5)
    box(ax,10.3,8.25,3.2,1.25,'UNKNOWN\nBuzzer tắt ngay',12)
    arrow(ax,[(8.04,8.25),(8.66,8.25)])
    label(ax,8.38,8.82,'Không',10)
    arrow(ax,[(4.3,7.58),(4.3,7.12),(6,7.12),(6,6.95)])
    label(ax,3.7,7.2,'Có',10)
    box(ax,6,6.08,10.6,1.65,'E1: hai mắt nhắm liên tục ≥1,5 s\nE2: ngáp ≥2 đợt / 60 s\nE3: blink hiện tại ≥4 và tăng ≥1 trong hai cửa sổ 5 s đầy đủ',11.5)
    for x in (2,6,10):
        arrow(ax,[(6,5.23),(6,4.6),(x,4.6),(x,4.18)])
    box(ax,2,3.35,3.35,1.6,'E1 hoặc (E2 và E3)\nALERT\nBật buzzer',12)
    box(ax,6,3.35,3.35,1.6,'Chỉ E2 hoặc E3\nWARNING\nBuzzer tắt',12)
    box(ax,10,3.35,3.35,1.6,'Không có E1/E2/E3\nNORMAL\nBuzzer tắt',11.5)
    box(ax,6,1.5,10.6,1.15,'Hồi phục: khi hết kích hoạt, giữ ALERT tới đủ 1 s quan sát hợp lệ\nUNKNOWN luôn tắt ngay; ngáp hợp lệ có thể được ghi riêng khi mắt chưa rõ',10.8)
    save(fig,'alert_decision_design')


def serial_sequence():
    fig, ax = canvas(9.0)
    for x, text in ((2.0,'PC / Radxa\nSerialAlertSink'),(6,'ESP32\nFirmware'),(10,'Buzzer active\nNgõ điều khiển')):
        box(ax,x,8.1,3.2,1.0,text,11.5)
        ax.plot([x,x],[7.55,.8],color='#8a949c',lw=1,ls='--')
    arrow(ax,[(2,7.0),(6,7.0)])
    label(ax,4,7.35,'ALERT 1 <reasons>',11)
    arrow(ax,[(6,7.0),(10,7.0)])
    label(ax,8,7.35,'GPIO25 = HIGH → bật',10.5)
    arrow(ax,[(6,6.15),(2,6.15)])
    label(ax,4,6.5,'OK ALERT 1',11)
    arrow(ax,[(2,5.25),(6,5.25)])
    label(ax,4,5.6,'Heartbeat: lặp trạng thái mỗi 0,5 s',10)
    arrow(ax,[(2,4.4),(6,4.4)])
    label(ax,4,4.75,'ALERT 0 khi hết cảnh báo / thoát',10)
    arrow(ax,[(6,4.4),(10,4.4)])
    label(ax,8,4.75,'GPIO25 = LOW → tắt',10.5)
    arrow(ax,[(6,3.6),(2,3.6)])
    label(ax,4,3.94,'OK ALERT 0',11)
    ax.plot([.4,11.6],[2.95,2.95],color=INK,lw=.8)
    label(ax,6,2.55,'Nhánh mất liên lạc — xét riêng khi buzzer đang bật',11)
    label(ax,3.8,1.8,'Không có lệnh hợp lệ\ntrong ≥2 giây',11)
    arrow(ax,[(6,1.65),(10,1.65)])
    label(ax,8,2.0,'Watchdog → LOW → tắt',10.5)
    label(ax,6,.45,'ACK xác nhận lệnh nhận được, không đo thời điểm phát âm thực tế.',10)
    save(fig,'serial_buzzer_sequence')


def software_design():
    fig, ax = canvas(8.8)
    box(ax,6,7.75,10.6,1.0,'CLI → runtime.py: đọc YAML / manifest, tải model, quản lý phiên',11.5)
    for x in (2,6,10):
        arrow(ax,[(6,7.23),(6,6.85),(x,6.85),(x,6.63)])
    box(ax,2,5.8,3.35,1.6,'capture.py\nCamera: frame mới nhất\nVideo: timestamp nguồn',10.8)
    box(ax,6,5.8,3.35,1.6,'vision.py + models.py\nYuNet / ROI / quality\nTorch · ONNX · RKNN',10.5)
    box(ax,10,5.8,3.35,1.6,'core.py\nObservation → Monitor\nStatus + nguyên nhân',10.8)
    arrow(ax,[(3.7,5.8),(4.25,5.8)])
    arrow(ax,[(7.7,5.8),(8.25,5.8)])
    label(ax,4,4.55,'Frame',10)
    label(ax,8,4.55,'Xác suất + thời gian',10)
    for x in (2,6,10):
        arrow(ax,[(10,4.97),(10,4.15),(x,4.15),(x,3.95)])
    box(ax,2,3.1,3.35,1.6,'alerting.py\nSerialAlertSink\nESP32 → buzzer',11)
    box(ax,6,3.1,3.35,1.6,'journal.py\nCSV theo frame\nJSONL + summary JSON',11)
    box(ax,10,3.1,3.35,1.6,'overlay.py\nHiển thị tùy chọn\nCamera / headless',11)
    box(ax,6,1.35,10.6,1.0,'Cùng giao diện và logic cho PC / Radxa\nBackend RKNN Lite2 đã có adapter; thực thi NPU trên bo chưa được nghiệm thu',11)
    save(fig,'software_module_design')


if __name__ == '__main__':
    overall()
    hardware()
    roi()
    radxa()
    eye_confirmation()
    yawn_confirmation()
    decision_design()
    serial_sequence()
    software_design()
    print('Created nine architecture/design figures (PNG + SVG):', OUT)
