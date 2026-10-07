"""Replay an open face changing angle through the complete video runtime."""
from dataclasses import asdict
import csv
import json
from pathlib import Path
import sys
import cv2
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from driver_monitor.config import load_config
from driver_monitor.models import sha256
from driver_monitor.runtime import run


def main():
    # Freeze the classifier that reproduced this pose bug. A later, better eye
    # model must not invalidate the motion-gate control by fixing its input.
    config = load_config(ROOT / "configs/camera_pc.yaml", headless=True,
                         manifest=ROOT / "models/smile_refined/manifest.json")
    image = cv2.imread(str(ROOT / "tests/fixtures/eye_motion/open_face.jpg"))
    height, width = image.shape[:2]
    # AVI codecs require even dimensions; pad at the far boundary only.
    image = cv2.copyMakeBorder(image, 0, height % 2, 0, width % 2, cv2.BORDER_REPLICATE)
    height, width = image.shape[:2]
    rotated = cv2.warpAffine(image, cv2.getRotationMatrix2D((width/2, height/2), 15, 1),
                             (width, height), borderMode=cv2.BORDER_REPLICATE)
    video = ROOT / "reports/head_motion_fixture.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"FFV1"), 15, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Lossless FFV1 video writer unavailable")
    for index in range(45):
        writer.write(rotated if 15 <= index <= 20 else image)
    writer.release()
    summaries = {}
    for label in ("previous_policy", "motion_gate"):
        settings = asdict(config)
        settings["manifest"] = str(config.manifest)
        settings["log_dir"] = str(ROOT / f"reports/eye_motion_replay/{label}")
        if label == "previous_policy":
            # Reproduce the old decision behavior using the same current
            # classifiers and pixels, without motion/open confirmation.
            settings["eye_motion_max_shift_ratio"] = 1.
            settings["eye_motion_max_roll_degrees"] = 90.
            settings["monitor"]["eye_event_open_seconds"] = 0.
        cfg = ROOT / f".cache/debug/eye_motion_{label}.yaml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(yaml.safe_dump(settings), encoding="utf-8")
        current = load_config(cfg)
        summary = run(current, video)
        frame_log = max(Path(current.log_dir).glob("*.csv"), key=lambda p:p.stat().st_mtime)
        with frame_log.open() as stream:
            rows = list(csv.DictReader(stream))
        summaries[label] = {"summary": summary, "frame_log": frame_log.relative_to(ROOT).as_posix(),
            "frame_log_sha256": sha256(frame_log), "config_sha256": current.fingerprint(),
            "eye_cycles_max": max(int(r["left_eye_events"]) + int(r["right_eye_events"]) for r in rows),
            "blink_total_max": max(int(r["blink_total"]) for r in rows),
            "motion_frames": sum(r["eye_quality"] == "head_motion" for r in rows)}
    report = {"type": "derived_open_face_pose_replay", "video_sha256": sha256(video),
              "note": "Still-image pose transforms, not natural blinking/video accuracy evidence", "results": summaries}
    (ROOT / "reports/eye_motion_replay.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k:{n:r[n] for n in ("eye_cycles_max", "blink_total_max", "motion_frames")} for k,r in summaries.items()}), flush=True)
    assert summaries["previous_policy"]["eye_cycles_max"] >= 1, "Fixture no longer reproduces the original error"
    assert summaries["motion_gate"]["eye_cycles_max"] == 0, "Moving open face counted as an eye cycle"
    assert summaries["motion_gate"]["blink_total_max"] == 0
    print("PASS: pose motion does not create eye events through full runtime", flush=True)


if __name__ == "__main__":
    main()
