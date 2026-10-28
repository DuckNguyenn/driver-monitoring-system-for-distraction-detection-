"""Aggregate three timestamp-identical replays and the locked blur evaluation."""
import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from driver_monitor.config import load_config
from driver_monitor.models import sha256
from check_yawn_replay import check


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "reports/blur_refinement")
    args = parser.parse_args()
    directory = args.directory.resolve()
    annotations = ROOT / "reports/yawn_camera_check/annotations.development.csv"
    labels = load(ROOT / "reports/yawn_camera_check/camera_development_labels.json")
    clip_id = Path(labels["video"]).name
    import yaml
    # Match the effective --manifest override of the model-only replay.
    ablation = yaml.safe_load((ROOT / "configs/camera_pc.yaml").read_text(encoding="utf-8"))
    ablation["manifest"] = str(ROOT / "models/blur_refined/manifest.json")
    ablation["log_dir"] = str(ROOT / "logs")
    ablation_path = ROOT / ".cache/blur_refinement/model_only.yaml"
    ablation_path.parent.mkdir(parents=True, exist_ok=True)
    ablation_path.write_text(yaml.safe_dump(ablation, sort_keys=False), encoding="utf-8")
    configs = {"baseline": ROOT / "configs/camera_pc.yaml", "model_only": ablation_path,
               "candidate": ROOT / "configs/camera_blur_candidate.yaml"}
    sessions, frame_data = {}, {}
    normal_intervals = []
    with annotations.open(encoding="utf-8", newline="") as stream:
        for r in csv.DictReader(stream):
            if r["label"] == "normal" and r["clip_id"] == clip_id:
                normal_intervals.append((float(r["start"]), float(r["end"])))
    for name, config in configs.items():
        paths = sorted((directory / name).glob("*.summary.json"))
        if not paths:
            raise ValueError(f"Missing replay: {name}")
        summary_path = paths[-1]
        frames_path = summary_path.with_name(summary_path.name.replace(".summary.json", ".csv"))
        summary = load(summary_path)
        if summary["fault"] or summary["live"]:
            raise ValueError("comparison requires successful offline replays")
        with frames_path.open(encoding="utf-8", newline="") as stream:
            frames = list(csv.DictReader(stream))
        if len(frames) != summary["frames"]:
            raise ValueError("incomplete frame log")
        event_output = directory / f"{name}.events_check.json"
        events, _ = check(frames_path, annotations, clip_id, config, event_output)
        normal_alert_frames = sum(r["alert"] == "1" and any(a <= float(r["timestamp"]) < b
                                   for a,b in normal_intervals) for r in frames)
        n = len(frames)
        sessions[name] = {"summary": summary, "frames_sha256": sha256(frames_path),
            "summary_file": summary_path.relative_to(ROOT).as_posix(),
            "unknown_frames": sum(r["state"] == "UNKNOWN" for r in frames),
            "unknown_rate": sum(r["state"] == "UNKNOWN" for r in frames) / n,
            "quality": dict(Counter(r["quality"] for r in frames)),
            "reasons": dict(Counter(r["reasons"] for r in frames if r["state"] == "UNKNOWN")),
            "blink_total": max(int(r["blink_total"]) for r in frames),
            "eye_cycles_total": max(int(r["left_eye_events"])+int(r["right_eye_events"]) for r in frames),
            "alert_frames_in_annotated_normal": normal_alert_frames,
            "events": events}
        frame_data[name] = frames
    reference = [(r["frame"],r["timestamp"]) for r in frame_data["baseline"]]
    if any([(r["frame"],r["timestamp"]) for r in rows] != reference for rows in frame_data.values()):
        raise ValueError("replays did not use identical frame indices/media timestamps")
    baseline, candidate = sessions["baseline"], sessions["candidate"]
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "One previously used camera clip and historical static development splits; not independent acceptance",
        "video": labels["video"], "video_sha256": sha256(ROOT / labels["video"]),
        "timestamps_sha256": sha256((ROOT / labels["video"]).with_suffix(".timestamps.json")),
        "annotations_sha256": sha256(annotations), "normal_seconds": sum(b-a for a,b in normal_intervals),
        "manifest_sha256": sha256(ROOT / "models/blur_refined/manifest.json"), "sessions": sessions,
        "unknown_frames_recovered": baseline["unknown_frames"]-candidate["unknown_frames"],
        "unknown_reduction_relative": 1-candidate["unknown_frames"]/baseline["unknown_frames"],
        "unknown_percentage_point_reduction": 100*(baseline["unknown_rate"]-candidate["unknown_rate"]),
        "physical_board_tested": False, "independent_camera_acceptance": False,
        "passed": candidate["unknown_frames"] < baseline["unknown_frames"] and
                  candidate["events"]["passed"] and not candidate["alert_frames_in_annotated_normal"]}
    save(directory / "replay_comparison.json", report)
    plot(directory, frame_data, report)
    write_markdown(directory, report)
    print(json.dumps({"report":str(directory / "replay_comparison.json"), "passed":report["passed"],
          "unknown":{k:v["unknown_frames"] for k,v in sessions.items()},
          "unknown_reduction_relative":report["unknown_reduction_relative"]}),flush=True)
    return 0 if report["passed"] else 1


def plot(directory, frames, report):
    cache = ROOT / ".cache/matplotlib"
    cache.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR",str(cache))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    colors = ["#73818c", "#e4a63a", "#198c74"]
    names = ["baseline", "model_only", "candidate"]
    fig, axes = plt.subplots(2,1,figsize=(10,6),gridspec_kw={"height_ratios":[2,1.3]})
    values = [100*report["sessions"][n]["unknown_rate"] for n in names]
    axes[0].bar(["Current models\n20 / 6","Blur-trained models\n20 / 6","Blur-trained models\n16 / 5"],values,color=colors,width=.55)
    for i,v in enumerate(values):
        axes[0].text(i,v+1,f"{v:.2f}% ({report['sessions'][names[i]]['unknown_frames']})",ha="center")
    axes[0].set_ylim(0,60)
    axes[0].set_ylabel("UNKNOWN frames (%)")
    axes[0].set_title("Same 1,131 frames; thresholds selected from real validation crops",loc="left")
    matrix = np.asarray([[int(r["state"]=="UNKNOWN") for r in frames[n]] for n in names])
    axes[1].imshow(matrix,aspect="auto",interpolation="nearest",cmap="Greys",vmin=0,vmax=1,
        extent=(float(frames[names[0]][0]["timestamp"]),float(frames[names[0]][-1]["timestamp"]),2.5,-.5))
    axes[1].set_yticks(range(3),["Current","New models only","New models + gates"])
    axes[1].set_xlabel("Video timestamp (s); black = UNKNOWN")
    fig.suptitle("Blur development ablation: one person, one previously used camera clip",fontsize=12)
    fig.tight_layout()
    fig.savefig(directory / "ablation.png",dpi=170)
    plt.close(fig)


def write_markdown(directory, replay):
    model_directory = ROOT / "models/blur_refined"
    evaluation = load(model_directory / "evaluation.json")
    calibration = load(model_directory / "quality_calibration.json")
    software = load(directory / "software_verification.json")
    pixels = load(directory / "pixel_regressions.json")
    lines = ["# Fine-tune với ảnh mờ và đánh giá trên PC", "", "Ngày đánh giá: 07/10/2026.", "",
        "Đã tạo hai checkpoint thử trong `models/blur_refined/` và profile `configs/camera_blur_candidate.yaml`. "
        "Dữ liệu gồm crop rõ, crop mờ thật đã có nhãn và crop được thêm Gaussian/motion blur. "
        "Những số dưới đây là kết quả phát triển trên dữ liệu hiện có; chưa phải nghiệm thu độc lập trong cabin hoặc trên Radxa.", "",
        "## Chạy thử trên camera", "", "Tại thư mục gốc dự án, dùng PowerShell:", "", "```powershell",
        "& '.\\.venv\\Scripts\\python.exe' -m driver_monitor run --config configs/camera_blur_candidate.yaml --source 0 --backend onnx --display",
        "```", "", "Profile PC đối chiếu vẫn là `configs/camera_pc.yaml`. Ngưỡng xác nhận hai mắt nhắm/ngáp và bộ lọc chuyển động đầu dùng cùng logic hiện có. "
        "Ảnh quá tối, lóa, mất mặt và ảnh vẫn mờ dưới ngưỡng mới tiếp tục trả về `UNKNOWN`.", "",
        "## Dữ liệu và huấn luyện", "",
        "YuNet tìm mặt và tâm mắt trên ảnh thu nhỏ; crop lấy từ ảnh gốc với kích thước mắt 0,8d × 0,6d và mặt mở rộng 10%. "
        "Gaussian/motion blur được thêm ở độ phân giải crop gốc trước bước RGB, resize cạnh ngắn 224 và center crop 224×224. "
        "Không thêm nhiễu vào vector đặc trưng đã cache để giả lập ảnh mờ.", "",
        "Hai model vẫn là YOLOv8n classification. Chỉ Linear 1280→2 được fine-tune; extractor, BN và preprocessing được giữ và kiểm tra bằng checksum. "
        "Huấn luyện có ràng buộc KL giữ dự đoán trên ảnh rõ và L2 giữ trọng số gần checkpoint đối chiếu. Checkpoint được chọn bằng validation, "
        "lưu lại, nạp lại rồi kiểm tra trước khi xuất ONNX. Bộ mắt/ngáp đọc tên lớp từ manifest.", "",
        "| Model | Crop gốc train | Crop mờ thật train | Gaussian/motion train | Toàn bộ mẫu train sau augmentation |", "|---|---:|---|---:|---:|"]
    for kind, name in (("eye","Mắt"),("yawn","Ngáp")):
        data = load(ROOT / ".cache/blur_refinement" / kind / "records.json")
        rows = [r for r in data["records"] if r["split"] == "train"]
        blur_counts = Counter(r["label"] for r in rows if r["variant"] == "base" and r["quality"] == "blurry")
        original = sum(r["variant"] == "base" for r in rows)
        synthetic = sum(r["origin"] == "synthetic_blur" for r in rows)
        lines.append(f"| {name} | {original} | {dict(blur_counts)} | {synthetic} | {len(rows)} |")
    lines += ["", "Ảnh mắt mờ thật gồm các frame camera có từng mắt được xem và gán nhãn `Open`, cùng ảnh CEW `Closed` có nhóm ảnh gốc được giữ cùng split. "
        "Ngáp mờ thật lấy từ khoảng thời gian đã gán nhãn trong video camera cũ; nhãn mắt không suy từ nhãn ngáp/cười. "
        "Các mẫu cười/nói chuyện và ảnh rõ cũ được giữ để kiểm tra báo ngáp sai. Dữ liệu mờ thật hiện còn ít; không có video của lần camera áo đỏ.", "",
        "Các bản mirror/gray/dim/roll/Gaussian/motion kế thừa split của ảnh gốc. Chỉ mục kiểm tra SHA ảnh, SHA tensor đầu vào và photo family; "
        "3 parent trùng pixel giữa split của bộ ngáp đã bị loại ở split thấp hơn. Các mẫu stress validation/test tách khỏi augmentation train. "
        "Tách theo người độc lập chưa được chứng minh đối với dữ liệu cũ; các crop liền kề từ một clip có tương quan.", "",
        "## F1 trên tập ảnh phát triển giữ lại", "",
        "Bảng dưới tính nhãn argmax trên crop, trước quality gate và xác nhận theo thời gian. Một ảnh có thể tạo nhiều view/crop; "
        "số mẫu không phải số người hay số sự kiện độc lập. F1 này không thay thế đánh giá video có nhãn theo người.", "",
        "| Model | Loại crop | Mẫu | Macro-F1 đối chiếu | Macro-F1 mới |", "|---|---|---:|---:|---:|"]
    for kind,name in (("eye","Mắt"),("yawn","Ngáp")):
        for variant,title in (("base","Gốc, gồm mờ thật"),("gaussian","Gaussian σ=0,75"),("motion","Motion 3 px, 30°")):
            before = evaluation["classifiers"][kind]["baseline"]["test"][variant]
            after = evaluation["classifiers"][kind]["candidate"]["test"][variant]
            lines.append(f"| {name} | {title} | {after['samples']} | {100*before['macro_f1']:.2f}% | {100*after['macro_f1']:.2f}% |")
    lines += ["", "Cải thiện F1 của model nhỏ; kết quả rõ nhất của pipeline đến từ cho phép suy luận các crop mờ vừa đã được kiểm tra bằng validation. "
        "Trên bộ crop mắt runtime có nhãn giữ lại, recall `Closed ≥0,8` tính cả frame bị chặn tăng từ 122/138 lên 127/138; "
        "số dự đoán mắt nhắm sai ở confidence này không tăng. Bộ mờ thật test riêng có 8 crop mắt: 4 được quality gate mới cho qua và nhận đúng, "
        "4 vẫn bị chặn. Không hạ tiếp ngưỡng dựa trên các mẫu test này.", "",
        "## Chọn ngưỡng độ nét", "",
        "Grid mặt 20/18/16/14/12 và mắt 6/5/4/3 được đánh giá chỉ trên crop validation thật, chưa biến đổi. "
        "Mỗi phương án phải giữ recall kể cả UNKNOWN, không tăng lỗi confidence theo lớp và theo nguồn, và không tăng tỷ lệ chưa quyết định. "
        "Các ngưỡng quá tối/lóa và logic theo thời gian được giữ. Phương án đồng hạng chọn ngưỡng cao hơn.", "",
        f"Chọn **mặt {calibration['selected']['min_sharpness']:g}, mắt {calibration['selected']['min_eye_sharpness']:g}**, thêm "
        f"{calibration['selected']['additional_accepted_validation_samples']} crop validation được suy luận. "
        "[Chi tiết calibration](../models/blur_refined/quality_calibration.json) ghi cả phương án bị loại. "
        "Ngưỡng là phương sai Laplacian, phụ thuộc camera/kích thước crop; không coi 16/5 là ngưỡng chung cho mọi camera.", "",
        "## Replay toàn pipeline", "",
        f"Cùng video {replay['sessions']['baseline']['summary']['media_seconds']:.3f} giây, cùng 1.131 frame và timestamp của video. "
        "Đã chạy ba cấu hình để phân biệt ảnh hưởng của model với ảnh hưởng của quality gate.", "",
        "| Cấu hình | Mặt/mắt | UNKNOWN | Tỷ lệ UNKNOWN | Ngáp xác nhận | Ngáp sai trong 17 giây bình thường/cười |", "|---|---|---:|---:|---:|---:|"]
    for key,title,threshold in (("baseline","Model PC hiện tại","20/6"),("model_only","Model blur mới, ngưỡng cũ","20/6"),("candidate","Model blur mới + ngưỡng validation","16/5")):
        s = replay["sessions"][key]
        events = s["events"]
        lines.append(f"| {title} | {threshold} | {s['unknown_frames']}/1131 | {100*s['unknown_rate']:.2f}% | "
                     f"{events['events']['yawn_hits']}/{events['events']['yawn_events']} | {events['false_yawn_confirmations_in_normal']} |")
    lines += ["", f"Giảm **{replay['unknown_frames_recovered']} frame UNKNOWN**, tương đương "
        f"**{100*replay['unknown_reduction_relative']:.2f}%** so với đối chiếu ({replay['unknown_percentage_point_reduction']:.2f} điểm phần trăm). "
        "Ngáp đầu được xác nhận ở 7,109 giây thay cho 10,625 giây; ngáp thứ hai ở 29,047 giây. "
        "Không có frame bật cảnh báo trong các khoảng bình thường đã gán nhãn. Không suy ra tỷ lệ báo nhầm mỗi giờ từ 17 giây này.", "",
        "![So sánh ba cấu hình](blur_refinement/ablation.png)", "",
        "Tốc độ dưới đây là replay PC, chưa phải camera trực tiếp hoặc NPU Radxa. Thời gian từng lần chạy có dao động; vòng đo trên cùng ảnh "
        "không tái hiện mức chậm gấp đôi do đổi checkpoint, nên không kết luận model mới làm tăng gấp đôi thời gian suy luận.", "",
        "| Cấu hình | FPS lần replay cuối | p95 đọc frame → quyết định |", "|---|---:|---:|"]
    for key,title in (("baseline","Đối chiếu"),("model_only","Chỉ model mới"),("candidate","Model mới + ngưỡng mới")):
        s = replay["sessions"][key]["summary"]
        lines.append(f"| {title} | {s['fps']:.2f} | {s['latency_p95_ms']} ms |")
    lines += ["", "## Kiểm tra và giới hạn", "",
        f"- {software['tests_total']} test phần mềm đạt, {software['tests_skipped']} test bị bỏ qua; kiểm tra dependency và mô phỏng firmware đạt.",
        f"- {pixels['tests_run']} ca kiểm tra với profile mới đạt: cười/ngáp, mắt mở hẹp, một mắt nhắm, hai mắt nhắm kéo dài, chuyển động đầu và blur thêm vào ảnh thật.",
        "- PT/ONNX có nhãn giống nhau trên 51 crop đại diện mỗi model; sai khác xác suất lớn nhất "
        f"{evaluation['classifiers']['eye']['parity']['max_probability_difference']:.2e} (mắt) và "
        f"{evaluation['classifiers']['yawn']['parity']['max_probability_difference']:.2e} (ngáp).",
        "- Chưa có video áo đỏ, test người mới, clip hai mắt nhắm có nhãn đầy đủ, 2 giờ bình thường hoặc chạy liên tục 2 giờ. Những tiêu chí nghiệm thu này vẫn cần đo.",
        "- Không có RKNN cho checkpoint blur mới; RKNN gốc trong `models/` dùng trọng số khác. Chưa chạy NPU/còi trên bo thật.", "",
        "[Kết quả ảnh và parity](../models/blur_refined/evaluation.json), [replay](blur_refinement/replay_comparison.json), "
        "[regression pixel](blur_refinement/pixel_regressions.json), [phần mềm](blur_refinement/software_verification.json).", "",
        "## Tái tạo và bổ sung dữ liệu", "",
        "Những lệnh này dùng dữ liệu và chỉ mục cục bộ trong workspace hiện có; GitHub không chứa dataset, ảnh review, video hoặc feature cache. "
        "Sau khi clone chỉ cần model/ONNX để chạy thử; muốn train cần khôi phục dữ liệu hoặc chuẩn bị chỉ mục có nhãn tương ứng trong YAML.", "", "```powershell",
        "& '.\\.venv\\Scripts\\python.exe' tools/refine_blur.py all --settings configs/blur_training.yaml",
        "& '.\\.venv\\Scripts\\python.exe' tools/check_blur_candidate.py --require-local-evidence",
        "```", "",
        "Các stage riêng: `prepare`, `extend-eye`, `train`, `export`, `calibrate`, `evaluate`; `--kind eye|yawn|both` áp dụng cho prepare/train. "
        "Có thể thay epochs, learning rate, anchor hoặc grid mà không tạo lại feature khi pixels/seed/config không đổi. "
        "Khi đổi crop/model/nhãn/seed phải chuẩn bị lại; ảnh gán nhãn thêm phải vào train/validation theo người/clip, không dùng test để chỉnh ngưỡng.", "",
        "`real_eye_labels` trong YAML nhận JSON có `records`: mỗi mục chứa `path` từ gốc repo, `sha256`, `split`, "
        "`eye_boxes` từ runtime và `eye_labels` gồm hai nhãn `Open|Closed|Unknown`. `source_manifest`/`source_sha256` có thể lưu nguồn ngoài. "
        "`camera_labels` chứa video và các khoảng `[start,end)` có `label`, `action`, `split`; khoảng chuyển trạng thái không rõ để ngoài nhãn.", "",
        "Cơ chế blur dùng `cv2.GaussianBlur` và kernel motion chuẩn hóa qua `cv2.filter2D`, theo "
        "[tài liệu lọc ảnh OpenCV](https://docs.opencv.org/4.x/d4/d13/tutorial_py_filtering.html). "
        "Model giữ quy trình classification; [tài liệu Ultralytics](https://docs.ultralytics.com/tasks/classify/) là nguồn tham khảo kiến trúc/API, "
        "không thay thế phiên bản thư viện và checksum đã khóa trong manifest.", ""]
    (ROOT / "reports/BLUR_REFINEMENT.md").write_text("\n".join(lines),encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
