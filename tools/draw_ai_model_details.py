"""Draw model details from the inspected artifacts, without camera images."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = ROOT / "report_assets/model_architecture"
INK = "#203746"


def canvas(height):
    fig, ax = plt.subplots(figsize=(12, height))
    ax.set(xlim=(0, 12), ylim=(0, height))
    ax.axis("off")
    fig.subplots_adjust(left=.015, right=.985, bottom=.02, top=.98)
    return fig, ax


def box(ax, x, y, w, h, text, color="#eef4f6", size=10.5):
    ax.add_patch(FancyBboxPatch((x-w/2, y-h/2), w, h,
        boxstyle="round,pad=.025,rounding_size=.08", facecolor=color,
        edgecolor=INK, linewidth=1.05))
    ax.text(x, y, text, ha="center", va="center", color=INK,
            fontfamily="DejaVu Sans", fontsize=size, linespacing=1.35)


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>",
                               mutation_scale=13, color=INK, linewidth=1.2))


def label(ax, x, y, text, size=11, weight="normal"):
    ax.text(x, y, text, ha="center", va="center", color=INK,
            fontsize=size, fontfamily="DejaVu Sans", weight=weight)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=220, facecolor="white")
    fig.savefig(OUT / f"{name}.svg", facecolor="white")
    plt.close(fig)


def yunet():
    fig, ax = canvas(8.4)
    label(ax, 6, 8.08, "YuNet 2023mar · graph ONNX đang dùng", 14, "bold")
    label(ax, 6, 7.68, "Kích thước dưới đây theo đầu vào OpenCV DNN 320 × 320", 11)
    box(ax, 2.0, 6.95, 3.4, .95,
        "Ảnh BGR 3 × 320 × 320\nConv 3×3, stride 2\nConv 1×1 + DWConv / MaxPool", size=10)
    label(ax, 2, 6.20, "BACKBONE", 11, "bold")
    label(ax, 6, 6.20, "HỢP NHẤT ĐẶC TRƯNG", 11, "bold")
    label(ax, 10, 6.20, "ĐẦU DỰ ĐOÁN", 11, "bold")
    for y, stride, spatial in ((5.45, 8, 40), (4.0, 16, 20), (2.55, 32, 10)):
        box(ax, 2, y, 3.4, 1.05,
            f"B{stride} · stride {stride}\n64 × {spatial} × {spatial}")
        if stride == 32:
            text = "P32\nConv 1×1 → DWConv 3×3"
        else:
            text = f"P{stride}\nCộng B{stride} với P{stride*2} phóng ×2\nConv 1×1 → DWConv 3×3"
        box(ax, 6, y, 3.65, 1.05, text, "#e4f1ed", size=10)
        box(ax, 10, y, 3.4, 1.05,
            f"{spatial*spatial} vị trí\ncls: 1 · obj: 1\nbbox: 4 · kps: 10", "#fff2dc", size=10)
        arrow(ax, (3.73, y), (4.15, y))
        arrow(ax, (7.86, y), (8.27, y))
        ax.plot([11.73, 11.92], [y, y], color=INK, linewidth=1.2)
    ax.plot([11.92, 11.92], [5.45, 1.22], color=INK, linewidth=1.2)
    arrow(ax, (11.92, 1.22), (11.67, 1.22))
    arrow(ax, (3.2, 6.46), (3.2, 5.99))
    arrow(ax, (2, 4.90), (2, 4.55))
    arrow(ax, (2, 3.45), (2, 3.10))
    arrow(ax, (6, 3.10), (6, 3.45))
    arrow(ax, (6, 4.55), (6, 4.90))
    box(ax, 6, 1.22, 11.3, .9,
        "Giải mã → điểm tin cậy → NMS → đổi tọa độ về ảnh gốc\n"
        "Mỗi mặt: bbox (4) + 5 điểm mốc (10) + score (1)", size=11)
    label(ax, 6, .42,
          "DWConv: tích chập theo kênh. 53 nút Conv; 53.104 phần tử trọng số/bias Conv đã xuất.", 10)
    save(fig, "yunet_architecture")


def finetuning():
    fig, ax = canvas(7.0)
    label(ax, 6, 6.62, "Phạm vi fine-tune · giữ nguyên kiến trúc YOLOv8n-cls", 14, "bold")
    label(ax, 6, 6.18, "Mỗi model: 1.440.850 tham số · dữ liệu vào RGB 224 × 224", 11)
    label(ax, 2.05, 5.62, "BACKBONE", 11, "bold")
    label(ax, 6, 5.62, "PHẦN ĐẦU CLASSIFY", 11, "bold")
    label(ax, 10, 5.62, "LINEAR 1.280 → 2", 11, "bold")
    rows = ((4.67, "Mắt · eye_refined_v4", True),
            (2.98, "Ngáp · camera / USB", False),
            (1.29, "Blur · mắt và ngáp", False))
    for y, title, tail_train in rows:
        label(ax, 6, y+.68, title, 11.5, "bold")
        box(ax, 2.05, y, 3.45, 1.0,
            "Conv + C2f\n1.108.048 tham số\nGiữ trọng số", size=10.5)
        box(ax, 6, y, 3.65, 1.0,
            "Conv 1×1 + BN → GAP\n330.240 tham số\n" +
            ("Cập nhật Conv / affine BN" if tail_train else "Giữ trọng số"),
            "#fff2dc" if tail_train else "#eef4f6", size=10)
        box(ax, 10, y, 3.4, 1.0,
            "2.562 tham số\nCập nhật trọng số / bias\nSoftmax khi suy luận", "#fff2dc", size=10.5)
        arrow(ax, (3.80, y), (4.14, y))
        arrow(ax, (7.86, y), (8.27, y))
    label(ax, 6, .38,
          "Màu vàng: tham số được huấn luyện. Thống kê chạy BatchNorm giữ cố định; GAP không có tham số.", 10)
    save(fig, "finetuning_architecture")


if __name__ == "__main__":
    yunet()
    finetuning()
    print("Saved YuNet and fine-tuning diagrams (PNG + SVG)")
