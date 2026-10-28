import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
from driver_monitor.capture import Frame
from driver_monitor.config import Config
from driver_monitor.runtime import run


class RuntimeTests(unittest.TestCase):
    def test_display_and_dashboard_receive_the_same_annotated_driver_monitor_frame(self):
        source_frame = np.full((480, 640, 3), 90, np.uint8)
        sent, displayed = [], []
        class Classifier:
            def __init__(self, _, name, *args): self.name = name
            def predict(self, _): return {"Closed": .01, "Open": .99} if self.name == "eye" else {"yawn": .01, "no_yawn": .99}
            def close(self): pass
        capture = SimpleNamespace(live=False, error=None, eof=False,
            read=lambda: Frame(0., source_frame, time.monotonic(), 0), close=lambda: None)
        vision = SimpleNamespace(observe=lambda _, **kwargs: SimpleNamespace(quality="usable", eye_quality="usable",
            crops=(source_frame,)*3, boxes=((100,100,300,350),), metrics={}, track_changed=False))
        observer = SimpleNamespace(start=lambda *_: None, record=lambda record, frame, boxes: sent.append(frame),
            fault=lambda *_: None, end=lambda *_: None)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "test.avi"); source.write_bytes(b"synthetic source")
            config = Config(log_dir=Path(directory,"logs"), headless=False, max_frames=1)
            with patch("driver_monitor.runtime.Vision",return_value=vision), patch("driver_monitor.runtime.Classifier",Classifier), \
                    patch("driver_monitor.runtime.Capture",return_value=capture), \
                    patch("driver_monitor.runtime.cv2.imshow",side_effect=lambda _,frame:displayed.append(frame)), \
                    patch("driver_monitor.runtime.cv2.waitKey",return_value=-1), patch("driver_monitor.runtime.cv2.destroyAllWindows"):
                run(config, source, observer=observer)
        self.assertEqual(len(sent), 1)
        self.assertIs(sent[0], displayed[0], "Web/app must receive the rendered Driver monitor view")
        self.assertFalse(np.array_equal(sent[0], source_frame), "Overlay includes panels and metrics")
        self.assertTrue(np.all(source_frame == 90), "Inference source pixels remain intact")

    def test_missing_model_startup_fault_is_persisted_without_opening_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            config = Config(manifest=directory / "missing.json", log_dir=directory / "logs")
            with patch("driver_monitor.runtime.Capture") as capture:
                with self.assertRaises(FileNotFoundError):
                    run(config, "0")
                capture.assert_not_called()
            summary = json.loads(next(config.log_dir.glob("*.summary.json")).read_text())
            self.assertEqual(summary["frames"], 0)
            self.assertIn("FileNotFoundError", summary["fault"])
            events = [json.loads(line) for line in next(config.log_dir.glob("*.jsonl")).read_text().splitlines()]
            fault = next(e for e in events if e["event"] == "runtime_fault")
            self.assertEqual(fault["state"], "UNKNOWN")
            self.assertFalse(fault["alert"])

    def test_runtime_fault_cleans_up_an_active_alert(self):
        crop = np.full((48, 64, 3), 80, np.uint8)
        class FakeClassifier:
            instances = []
            def __init__(self, manifest, name, *args):
                self.name, self.closed = name, False
                self.instances.append(self)
            def predict(self, _):
                return {"Closed": .9, "Open": .1} if self.name == "eye" else {"yawn": .1, "no_yawn": .9}
            def close(self): self.closed = True
        class FakeCapture:
            live, eof, error = False, False, None
            def __init__(self, *args): self.index, self.closed = 0, False
            def read(self):
                if self.index == 17:
                    raise RuntimeError("capture failure after alarm")
                packet = Frame(self.index / 10, crop, time.monotonic(), self.index)
                self.index += 1
                return packet
            def close(self): self.closed = True
        class FakeSink:
            last_error = None
            def __init__(self): self.calls, self.closed = [], False
            def set_alert(self, active, reasons=()): self.calls.append(bool(active))
            def close(self): self.closed = True
        vision = SimpleNamespace(observe=lambda _, **kwargs: SimpleNamespace(quality="usable", eye_quality="usable", crops=(crop, crop, crop), boxes=(), metrics={}, track_changed=False))
        capture, sink = FakeCapture(), FakeSink()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "test.avi"
            source.write_bytes(b"synthetic capture transport")
            config = Config(log_dir=directory / "logs")
            with patch("driver_monitor.runtime.Vision", return_value=vision), patch("driver_monitor.runtime.Classifier", FakeClassifier), patch("driver_monitor.runtime.Capture", return_value=capture), patch("driver_monitor.runtime.NullAlertSink", return_value=sink):
                with self.assertRaisesRegex(RuntimeError, "capture failure"):
                    run(config, source, observer=SimpleNamespace(start=lambda *_: None,
                        record=lambda *_: (_ for _ in ()).throw(OSError("dashboard unavailable")),
                        fault=lambda *_: None, end=lambda *_: None))
            self.assertIn(True, sink.calls)
            self.assertFalse(sink.calls[-1])
            self.assertTrue(sink.closed)
            self.assertTrue(capture.closed)
            self.assertTrue(all(model.closed for model in FakeClassifier.instances))
            summary = json.loads(next(config.log_dir.glob("*.summary.json")).read_text())
            self.assertIn("capture failure", summary["fault"])
