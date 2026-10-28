"""The dashboard indexes evidence without modifying or duplicating it."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from driver_monitor.dashboard_history import HistoryIndex
from driver_monitor.dashboard_data import snapshot


class HistoryTests(unittest.TestCase):
    def test_missing_counter_does_not_create_duplicate_events_after_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            rows=[{'event':'status','state':'NORMAL','yawn_count':value,'blink_total':value} for value in (0,1,None,1,2)]
            (root/'abc.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
            history=HistoryIndex(root/'history.sqlite3',root)
            try:
                history.scan()
                kinds=[event['kind'] for event in history.events('abc')]
                self.assertEqual(kinds.count('yawn'),2)
                self.assertEqual(kinds.count('blink'),2)
                self.assertIsNone(history.series('abc')[2]['counts']['yawn_60s'])
            finally:history.close()

    def test_bad_history_fields_do_not_poison_valid_series_or_events(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = [
                {"event": {}},
                {"event": "status", "state": None, "yawn_count": None, "blink_total": None,
                 "reasons": {"bad": 1}, "observation": {"quality": 4, "eye_quality": []}},
                {"event": "status", "state": "NORMAL", "yawn_count": 0, "blink_total": 0},
                {"event": "status", "state": "ALERT", "alert": True, "yawn_count": 1, "blink_total": 1},
            ]
            log = root / "abc.jsonl"
            log.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
            original = log.read_bytes()
            history = HistoryIndex(root / 'history.sqlite3', root)
            try:
                history.scan()
                self.assertTrue(history.errors)
                values = history.series('abc')
                self.assertEqual(len(values), 3)
                self.assertEqual(values[0]['state'], 'UNKNOWN')
                self.assertEqual(values[0]['quality']['image'], 'unavailable')
                self.assertIsNone(values[0]['counts']['yawn_60s'])
                self.assertEqual(values[-1]['state'], 'ALERT')
                kinds = [event['kind'] for event in history.events('abc')]
                self.assertEqual(kinds.count('alert'), 1)
                self.assertEqual(kinds.count('yawn'), 1)
                self.assertEqual(kinds.count('blink'), 1)
                self.assertIn('ALERT', history.export_csv('abc'))
                self.assertEqual(log.read_bytes(), original)
            finally:
                history.close()

    def test_missing_file_during_scan_does_not_hide_other_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'valid.jsonl').write_text('{"event":"startup"}\n', encoding='utf-8')
            history = HistoryIndex(root/'history.sqlite3', root)
            try:
                with patch.object(Path, 'glob', return_value=iter([root/'missing.jsonl', root/'valid.jsonl'])):
                    history.scan()
                self.assertIsNotNone(history.session('valid'))
                self.assertTrue(history.errors)
            finally:
                history.close()

    def test_replaced_log_rebuilds_only_derived_rows_and_keeps_source_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = root/'abc.jsonl'
            log.write_text('{"event":"status","state":"NORMAL","note":"old tail and padding"}\n',encoding='utf-8')
            other = root/'other.jsonl'
            other.write_text('{"event":"startup"}\n',encoding='utf-8')
            history = HistoryIndex(root/'history.sqlite3',root)
            try:
                history.scan()
                log.write_text('{"event":"status","state":"ALERT","alert":true}\n',encoding='utf-8')
                replacement = log.read_bytes()
                history.scan();history.scan()
                self.assertEqual([row['state'] for row in history.series('abc')],['ALERT'])
                self.assertEqual(sum(e['kind']=='alert' for e in history.events('abc')),1)
                self.assertIsNotNone(history.session('other'))
                self.assertEqual(log.read_bytes(),replacement)
                # Replacement can also be longer than the old cursor.
                log.write_text('{"event":"status","state":"UNKNOWN","reasons":["no_face"],"padding":"longer replacement record to retain no obsolete alert"}\n',encoding='utf-8')
                history.scan()
                self.assertEqual([row['state'] for row in history.series('abc')],['UNKNOWN'])
                self.assertFalse(any(e['kind']=='alert' for e in history.events('abc')))
            finally:
                history.close()

    def test_partial_legacy_record_does_not_invent_zero_counts(self):
        value = snapshot({"observation": {"quality": None}}, "abc", 1)
        self.assertEqual(value["quality"]["image"], "unavailable")
        self.assertIsNone(value["counts"]["blink_total"])
        self.assertIsNone(value["counts"]["eye_cycles"])
        self.assertIsNone(value["probabilities"]["eye_1_closed"])

    def test_incomplete_tail_and_restart_do_not_drop_or_duplicate_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = root / "abc.jsonl"
            first = json.dumps({"event": "startup", "utc": "2026-10-08T01:00:00+00:00"}) + "\n"
            log.write_text(first + '{"event":"runtime_fault",', encoding="utf-8")
            history = HistoryIndex(root / "history.sqlite3", root)
            history.scan()
            self.assertEqual(len(history.events("abc")), 1)
            history.close()
            with log.open("a", encoding="utf-8") as target:
                target.write('"error":"missing model"}\n')
            history = HistoryIndex(root / "history.sqlite3", root)
            history.scan()
            history.scan()
            self.assertEqual(len(history.events("abc")), 2)
            self.assertEqual(history.session("abc")["lifecycle"], "error")
            history.close()

    def test_reimport_preserves_one_session_and_one_alert_event(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = root / "session-a.jsonl"
            rows = [
                {"event": "session_start", "utc": "2026-10-08T10:00:00+00:00", "source": "0", "live": True, "backend": "onnx"},
                {"event": "status", "utc": "2026-10-08T10:00:02+00:00", "timestamp": 10.0,
                 "state": "ALERT", "alert": True, "reasons": ["prolonged_eye_closure"],
                 "blink_total": 0, "yawn_count": 0, "yawn_state": "no_yawn",
                 "observation": {"quality": "usable", "left_eye": {"Closed": .95, "Open": .05}, "right_eye": None},
                 "fps": 25.0, "latency_ms": 18.0},
                {"event": "session_end", "utc": "2026-10-08T10:00:03+00:00", "frames": 75, "fault": None},
            ]
            original = "".join(json.dumps(row) + "\n" for row in rows).encode()
            log.write_bytes(original)
            history = HistoryIndex(root / "history.sqlite3", root)
            try:
                history.scan()
                history.scan()
                sessions = history.sessions()
                self.assertEqual(len(sessions), 1)
                self.assertEqual(sessions[0]["id"], "session-a")
                self.assertEqual(sessions[0]["source_kind"], "camera")
                self.assertEqual(sessions[0]["lifecycle"], "finished")
                self.assertEqual(len(history.series("session-a")), 1)
                alerts = [e for e in history.events("session-a") if e["kind"] == "alert"]
                self.assertEqual(len(alerts), 1)
                self.assertEqual(log.read_bytes(), original)
            finally:
                history.close()
