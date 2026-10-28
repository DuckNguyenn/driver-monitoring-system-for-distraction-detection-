import queue
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from driver_monitor.dashboard_transport import DashboardPublisher


class TransportTests(unittest.TestCase):
    def test_slow_jpeg_encoder_does_not_hold_up_monitor_telemetry(self):
        import cv2
        import numpy as np
        import time
        statuses, frames = queue.Queue(1), queue.Queue(1)
        publisher = DashboardPublisher(statuses, frames, SimpleNamespace(value=time.monotonic()+10))
        publisher.start("camera", {"live": True})
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        original = cv2.imencode
        def blocked(*args):
            entered.set()
            release.wait(2)
            return original(*args)
        def submit():
            publisher.record({"state":"NORMAL"}, np.zeros((480,640,3),np.uint8))
            returned.set()
        with patch("cv2.imencode",side_effect=blocked):
            producer = threading.Thread(target=submit)
            producer.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertTrue(returned.wait(.2), "JPEG work must not block the AI callback")
                publisher.record({"state":"ALERT","alert":True})
                self.assertTrue(statuses.get_nowait()["alert"])
            finally:
                release.set()
                producer.join(2)
                publisher.end({})

    def test_preview_is_demand_driven_bounded_and_does_not_change_source_pixels(self):
        import cv2
        import numpy as np
        channels = queue.Queue(4), queue.Queue(1)
        demand, now = SimpleNamespace(value=0), [100.]
        publisher = DashboardPublisher(*channels, demand, preview_fps=5, clock=lambda: now[0])
        publisher.start("abc", {"live": True})
        source = np.zeros((900, 1200, 3), np.uint8)
        record = {"state": "NORMAL"}
        publisher.record(record, source, ((10, 10, 200, 200),))
        self.assertTrue(channels[1].empty())
        demand.value = 102.
        publisher.record(record, source, ((10, 10, 200, 200),))
        preview = channels[1].get(timeout=1)
        decoded = cv2.imdecode(np.frombuffer(preview["jpeg"], np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape[:2], (480, 640))
        self.assertTrue(np.any(decoded))
        self.assertFalse(np.any(source))
        now[0] += .1
        publisher.record(record, source)
        try:
            with self.assertRaises(queue.Empty):
                channels[1].get(timeout=.04)
        finally:
            publisher.close()

    def test_full_channel_keeps_latest_decision_and_one_alert_episode(self):
        statuses, frames = queue.Queue(1), queue.Queue(1)
        publisher = DashboardPublisher(statuses, frames, SimpleNamespace(value=0), status_interval=0)
        publisher.start("session-a", {"source": "0", "live": True, "backend": "onnx", "config": {"serial_port": None}})
        record = {"state": "ALERT", "alert": True, "timestamp": 5, "reasons": ["prolonged_eye_closure"],
                  "observation": {"quality": "usable", "left_eye": {"Closed": .95, "Open": .05}, "right_eye": None}}
        publisher.record(record)
        first = statuses.get_nowait()
        self.assertEqual(first["state"], "ALERT")
        self.assertEqual(first["probabilities"]["eye_1_closed"], .95)
        self.assertIsNone(first["probabilities"]["eye_2_closed"])
        self.assertEqual(first["devices"]["esp32"]["state"], "not_configured")
        statuses.put(first)
        publisher.record(record)
        second = statuses.get_nowait()
        self.assertEqual(first["alert_episode_id"], second["alert_episode_id"])
        self.assertTrue(frames.empty())
        publisher.end({"fault": "model failed"})
        terminal = statuses.get_nowait()
        self.assertEqual(terminal["state"], "UNKNOWN")
        self.assertFalse(terminal["alert"])
        self.assertEqual(terminal["lifecycle"], "error")
