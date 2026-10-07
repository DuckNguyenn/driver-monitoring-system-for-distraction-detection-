import csv
from pathlib import Path
import tempfile
import unittest
import json
from driver_monitor.config import ROOT, load_config
from driver_monitor.evaluation import read_annotations, evaluate_session, evaluate_study
from driver_monitor.models import sha256


class EvidenceTests(unittest.TestCase):
    def test_cli_paths_relative_to_cwd_and_yaml_paths_relative_to_yaml(self):
        config = load_config(ROOT / "configs/driver_monitor.yaml", log_dir="reports/example")
        self.assertEqual(config.log_dir, Path("reports/example").resolve())
        self.assertEqual(config.manifest, ROOT / "models/manifest.json")

    def test_subject_leakage_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "annotations.csv"
            path.write_text("subject_id,clip_id,split,lighting,start,end,label\np1,a.avi,train,day,0,2,normal\np1,b.avi,test,day,0,2,normal\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_annotations(path)

    def test_event_recall_and_normal_false_alarm_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            ann = directory / "annotations.csv"
            ann.write_text("subject_id,clip_id,split,lighting,start,end,label\np1,a.avi,test,day,0,3,eyes_closed\np1,a.avi,test,day,3,6,normal\n", encoding="utf-8")
            frames = directory / "frames.csv"
            with frames.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["timestamp", "reasons", "alert", "yawn_state", "yawn_count", "latency_ms", "state"])
                writer.writeheader()
                for i in range(61):
                    t = i / 10
                    active = 1.5 <= t < 3 or 4 <= t < 4.5
                    writer.writerow(dict(timestamp=t, reasons="eyes_closed_too_long" if active else "", alert=int(active), yawn_state="no_yawn", yawn_count=0, latency_ms=20, state="ALERT" if active else "NORMAL"))
            metadata = {"event": "session_start", "live": False, "source": "a.avi", "config_sha256": load_config().fingerprint()}
            frames.with_suffix(".jsonl").write_text(json.dumps(metadata) + "\n", encoding="utf-8")
            report = evaluate_session(frames, ann, "a.avi", directory / "report.json", load_config())
            self.assertEqual(report["closure_recall"], 1)
            self.assertEqual(report["false_alarm_count"], 1)
            self.assertEqual(report["reaction_p95_ms"], 20)
            metadata["config_sha256"] = "different"
            frames.with_suffix(".jsonl").write_text(json.dumps(metadata) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluate_session(frames, ann, "a.avi", directory / "report.json", load_config())

    def test_study_weights_event_counts_and_rejects_duplicate_clips(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            ann = directory / "annotations.csv"
            ann.write_text("subject_id,clip_id,split,lighting,start,end,label\np1,a.avi,test,day,0,5,normal\np2,b.avi,test,day,0,5,normal\n", encoding="utf-8")
            for clip, subject, count, hits, normal in (("a.avi", "p1", 1, 1, 100), ("b.avi", "p2", 9, 0, 900)):
                report = {"type": "annotated_clip", "clip_id": clip, "subject_id": subject, "split": "test", "lighting": "day", "config_sha256": "same", "annotations_sha256": sha256(ann), "closure_events": count, "closure_hits": hits, "yawn_events": 0, "yawn_hits": 0, "normal_seconds": normal, "false_alarm_count": 0, "frames": count, "reaction_delays_ms": [20] if hits else [], "unknown_frame_fraction": 0}
                (directory / f"{clip}.json").write_text(json.dumps(report))
            result = evaluate_study(directory, ann, directory / "study.json")
            self.assertEqual(result["overall"]["closure_recall"], .1)
            self.assertFalse(result["complete_data"])
            self.assertFalse(result["event_criteria_met"])
            self.assertEqual(len(result["by_subject"]), 2)
            (directory / "duplicate.json").write_text((directory / "a.avi.json").read_text())
            with self.assertRaises(ValueError):
                evaluate_study(directory, ann, directory / "study.json")
