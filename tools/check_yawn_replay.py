"""Check real timestamped replay logs against reviewed event annotations.

Unlike checking the siren alone, this rejects extra yawn confirmations during
normal/smile intervals. A one-person development replay is not a held-out study.
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
from driver_monitor.config import load_config
from driver_monitor.evaluation import evaluate_session, read_annotations


def check(frames_path, annotations_path, clip_id, config_path, output):
    config = load_config(config_path)
    events = evaluate_session(frames_path, annotations_path, clip_id, output.with_suffix(".events.json"), config)
    annotations = [r for r in read_annotations(annotations_path) if r["clip_id"] == clip_id]
    with frames_path.open(encoding="utf-8", newline="") as stream:
        frames = list(csv.DictReader(stream))
    confirmations, previous = [], 0
    for row in frames:
        count = int(row["yawn_count"])
        if count > previous and row["yawn_state"] == "yawn":
            confirmations.append(float(row["timestamp"]))
        previous = count
    unmatched = list(confirmations)
    for interval in (r for r in annotations if r["label"] == "yawn"):
        match = next((t for t in unmatched if interval["start"] <= t <= interval["end"]), None)
        if match is not None:
            unmatched.remove(match)
    normal_false = [t for t in confirmations if any(r["label"] == "normal" and r["start"] <= t < r["end"] for r in annotations)]
    passed = (events["yawn_events"] > 0 and events["yawn_hits"] == events["yawn_events"] and
              not unmatched and not normal_false)
    report = {"scope": "annotated development replay; does not establish subject independence",
              "events": events, "confirmation_seconds": confirmations,
              "false_yawn_confirmations_in_normal": len(normal_false),
              "unmatched_confirmation_seconds": unmatched, "passed": passed}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps({"output": str(output), "yawn_hits": events["yawn_hits"],
                      "expected_yawns": events["yawn_events"], "confirmation_seconds": confirmations,
                      "false_yawn_confirmations_in_normal": len(normal_false), "passed": passed}), flush=True)
    return report, frames


def plot_sessions(sessions, annotations_path, clip_id, target):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    annotations = [r for r in read_annotations(annotations_path) if r["clip_id"] == clip_id]
    fig, axes = plt.subplots(len(sessions) + 1, 1, figsize=(12, 3.1 * len(sessions) + 2), sharex=True,
                             gridspec_kw={"height_ratios": [2] * len(sessions) + [1]})
    colors = ("#8b4559", "#126d82")
    for index, (name, report, frames) in enumerate(sessions):
        ax = axes[index]
        times = [float(r["timestamp"]) for r in frames]
        raw = [float(r["yawn_raw_probability"]) if r["yawn_raw_probability"] else np.nan for r in frames]
        filtered = [float(r["yawn_probability"]) if r["yawn_probability"] else np.nan for r in frames]
        for interval in annotations:
            if interval["label"] == "yawn":
                ax.axvspan(interval["start"], interval["end"], color="#d8edcf", alpha=.55)
        ax.fill_between(times, 0, 1, where=[r["quality"] != "usable" for r in frames],
                        color="#a0a0a0", alpha=.18, label="Rejected image quality")
        ax.plot(times, raw, color=colors[index], alpha=.40, linewidth=.8, label="Raw P(yawn)")
        ax.plot(times, filtered, color=colors[index], linewidth=1.4, label="EMA P(yawn)")
        ax.axhline(.70, color="#c87619", linestyle="--", linewidth=1, label="Enter threshold 0.70")
        for t in report["confirmation_seconds"]:
            ax.axvline(t, color="#125125", linestyle=":", linewidth=1.4)
            ax.annotate(f"Confirmed {t:.2f}s", xy=(t, .80), xytext=(5, 0), textcoords="offset points",
                        fontsize=9, bbox={"facecolor": "white", "alpha": .75, "edgecolor": "none"})
        ax.set_title(f"{name}: {report['events']['yawn_hits']}/{report['events']['yawn_events']} annotated yawns confirmed", loc="left")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Yawn probability")
        ax.grid(alpha=.16)
        ax.legend(loc="upper left", ncol=4, fontsize=8)
        axes[-1].step(times, [int(r["yawn_count"]) for r in frames], where="post", color=colors[index], label=name)
    axes[-1].set_ylabel("Yawn count")
    axes[-1].set_xlabel("Recorded capture time (seconds)")
    axes[-1].set_yticks([0, 1, 2])
    axes[-1].grid(alpha=.2)
    axes[-1].legend(loc="upper left")
    fig.suptitle("Camera development replay: original vs repaired classifier\nGreen bands: reviewed yawns; normal intervals include smiling", fontsize=12)
    fig.tight_layout()
    fig.savefig(target, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/camera_pc.yaml")
    parser.add_argument("--annotations", type=Path, default=ROOT / "reports/yawn_camera_check/annotations.development.csv")
    parser.add_argument("--clip-id", default="20261007T070644_475102Z.avi")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-frames", type=Path)
    parser.add_argument("--baseline-config", type=Path, default=ROOT / "configs/camera_yawn_previous.yaml")
    args = parser.parse_args()
    report, frames = check(args.frames, args.annotations, args.clip_id, args.config, args.output)
    if args.baseline_frames:
        baseline, old_frames = check(args.baseline_frames, args.annotations, args.clip_id,
                                    args.baseline_config, args.output.with_name("baseline.regression.json"))
        if report["events"]["source_sha256"] != baseline["events"]["source_sha256"]:
            raise ValueError("Replay comparison uses different video bytes")
        if [r["timestamp"] for r in frames] != [r["timestamp"] for r in old_frames]:
            raise ValueError("Replay comparison uses different capture timestamps")
        plot_sessions([("Previous model", baseline, old_frames), ("Repaired model", report, frames)],
                      args.annotations, args.clip_id, args.output.with_suffix(".png"))
    raise SystemExit(0 if report["passed"] else 1)
