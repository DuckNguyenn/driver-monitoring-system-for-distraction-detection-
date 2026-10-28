import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from driver_monitor.dashboard_server import LiveHub, create_app
from driver_monitor.dashboard_transport import DashboardPublisher


class ApiTests(unittest.TestCase):
    def test_waiting_for_next_image_never_downloads_the_same_jpeg_again(self):
        with tempfile.TemporaryDirectory() as directory:
            hub=LiveHub(queue.Queue(4),queue.Queue(1),SimpleNamespace(value=0),clock=lambda:100.)
            hub.latest={"state":"NORMAL","lifecycle":"running"};hub.received=100.
            hub.preview={"time":100.,"sequence":7,"jpeg":b"first-frame"}
            with TestClient(create_app(directory,"test-code",hub)) as client:
                headers={"Authorization":"Bearer test-code"}
                repeated=client.get('/api/v1/frame.jpg?after=7',headers=headers)
                self.assertEqual(repeated.status_code,204)
                self.assertEqual(repeated.content,b'')
                hub.preview={"time":100.,"sequence":8,"jpeg":b"next-frame"}
                fresh=client.get('/api/v1/frame.jpg?after=7',headers=headers)
                self.assertEqual(fresh.status_code,200)
                self.assertEqual(fresh.content,b'next-frame')
                self.assertEqual(fresh.headers['X-Frame-Sequence'],'8')

    def test_malformed_legacy_log_does_not_prevent_api_startup_or_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=[{"event": {}}, {"event":"status","state":"NORMAL","observation":{"quality":4}}]
            Path(directory,'abc.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
            hub=LiveHub(queue.Queue(4),queue.Queue(1),SimpleNamespace(value=0))
            with TestClient(create_app(directory,'test-code',hub)) as client:
                headers={'Authorization':'Bearer test-code'}
                self.assertEqual(client.get('/api/v1/status',headers=headers).status_code,200)
                self.assertEqual(client.get('/api/v1/sessions/abc/series',headers=headers).status_code,200)
                self.assertEqual(client.get('/api/v1/sessions/abc/export.csv',headers=headers).status_code,200)

    def test_frame_metadata_is_authenticated_and_has_no_image_body(self):
        with tempfile.TemporaryDirectory() as directory:
            hub=LiveHub(queue.Queue(4),queue.Queue(1),SimpleNamespace(value=0),clock=lambda:100.)
            hub.latest={'state':'NORMAL','lifecycle':'running'};hub.received=100.
            hub.preview={'time':100.,'sequence':7,'jpeg':b'jpeg-bytes'}
            with TestClient(create_app(directory,'test-code',hub)) as client:
                self.assertEqual(client.head('/api/v1/frame.jpg').status_code,401)
                response=client.head('/api/v1/frame.jpg',headers={'Authorization':'Bearer test-code'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['X-Frame-Sequence'],'7')
                self.assertEqual(response.content,b'')
                self.assertEqual(client.get('/api/v1/frame.jpg',headers={'Authorization':'Bearer test-code'}).content,b'jpeg-bytes')
    def test_dev_browser_preflight_is_allowed_but_public_origins_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            hub = LiveHub(queue.Queue(4), queue.Queue(1), SimpleNamespace(value=0))
            with TestClient(create_app(directory, "test-code", hub)) as client:
                headers = {"Origin": "http://127.0.0.1:5182", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization"}
                good = client.options("/api/v1/status", headers=headers)
                self.assertEqual(good.status_code, 200)
                self.assertEqual(good.headers["access-control-allow-origin"], headers["Origin"])
                bad = client.options("/api/v1/status", headers={**headers, "Origin": "https://example.org"})
                self.assertNotIn("access-control-allow-origin", bad.headers)

    def test_every_data_route_requires_auth_and_websocket_auth_is_first_message(self):
        with tempfile.TemporaryDirectory() as directory:
            hub = LiveHub(queue.Queue(4), queue.Queue(1), SimpleNamespace(value=0))
            app = create_app(directory, "test-connection-code", hub)
            with TestClient(app) as client:
                for path in ("status", "sessions", "frame.jpg", "sessions/abc", "sessions/abc/series", "sessions/abc/events", "sessions/abc/export.csv"):
                    self.assertEqual(client.get("/api/v1/" + path).status_code, 401)
                headers = {"Authorization": "Bearer test-connection-code"}
                self.assertEqual(client.get("/api/v1/status", headers=headers).status_code, 200)
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect("/api/v1/ws") as ws:
                        ws.send_json({"type": "auth", "token": "wrong"})
                        ws.receive_json()
                with client.websocket_connect("/api/v1/ws") as ws:
                    ws.send_json({"type": "auth", "token": "test-connection-code"})
                    message = ws.receive_json()
                    self.assertEqual(message["type"], "snapshot")
                    self.assertIsNone(message["snapshot"])
                self.assertEqual(client.post("/api/v1/stop", headers=headers).status_code, 404)

    def test_stale_status_retains_nulls_and_preview_only_requests_when_viewed(self):
        demand = SimpleNamespace(value=0)
        statuses, frames = queue.Queue(4), queue.Queue(1)
        hub = LiveHub(statuses, frames, demand, clock=lambda: 100.)
        publisher = DashboardPublisher(statuses, frames, demand, status_interval=0, clock=lambda: 100.)
        publisher.start("abc", {"live": False, "source": "clip.avi", "backend": "onnx"})
        publisher.record({"timestamp": 6., "state": "UNKNOWN", "observation": {"quality": "blurry"}})
        hub.drain()
        self.assertEqual(demand.value, 0)
        self.assertEqual(hub.current()["source_kind"], "video")
        self.assertIsNone(hub.current()["probabilities"]["yawn"])
        hub.clock = lambda: 103.
        self.assertFalse(hub.current()["connected"])
        self.assertEqual(hub.current()["age_ms"], 3000.)

    def test_delayed_channel_delivery_does_not_make_an_old_snapshot_fresh(self):
        hub = LiveHub(queue.Queue(4), queue.Queue(1), SimpleNamespace(value=0), clock=lambda: 100.)
        hub.statuses.put({"state": "NORMAL", "lifecycle": "running", "_published_at": 97.})
        hub.drain()
        self.assertFalse(hub.current()["connected"])
        self.assertNotIn("_published_at", hub.current())

    def test_history_csv_and_missing_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "abc.jsonl"
            records = [{"event": "session_start", "utc": "2026-10-08T01:00:00+00:00", "live": False, "source": "clip.avi"},
                       {"event": "status", "utc": "2026-10-08T01:00:01+00:00", "timestamp": 1., "state": "UNKNOWN", "observation": {"quality": "blurry"}},
                       {"event": "session_end", "utc": "2026-10-08T01:00:02+00:00", "frames": 30}]
            path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
            hub = LiveHub(queue.Queue(4), queue.Queue(1), SimpleNamespace(value=0))
            with TestClient(create_app(directory, "test-code", hub)) as client:
                headers = {"Authorization": "Bearer test-code"}
                response = client.get("/api/v1/sessions", headers=headers).json()
                self.assertEqual(response["items"][0]["source_kind"], "video")
                rows = client.get("/api/v1/sessions/abc/series", headers=headers).json()["items"]
                self.assertIsNone(rows[0]["probabilities"]["eye_1_closed"])
                exported = client.get("/api/v1/sessions/abc/export.csv", headers=headers)
                self.assertEqual(exported.status_code, 200)
                self.assertIn("UNKNOWN", exported.text)
                self.assertEqual(client.get("/api/v1/sessions/missing/events", headers=headers).status_code, 404)
