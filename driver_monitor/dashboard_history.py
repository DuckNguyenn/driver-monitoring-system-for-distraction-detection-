"""Incremental, restart-safe read-only indexing of original JSONL evidence."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import threading

from .dashboard_data import count, normalize_record, snapshot


class HistoryIndex:
    def __init__(self, database, log_dir):
        self.log_dir = Path(log_dir)
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(database, check_same_thread=False, timeout=2)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, started_at TEXT, ended_at TEXT, source TEXT,
                source_kind TEXT NOT NULL DEFAULT 'unknown', backend TEXT, lifecycle TEXT NOT NULL DEFAULT 'initializing',
                metadata TEXT NOT NULL DEFAULT '{}', summary TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS records(session_id TEXT, offset INTEGER, utc TEXT, event TEXT, payload TEXT,
                PRIMARY KEY(session_id, offset));
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, session_id TEXT, utc TEXT, kind TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS imports(path TEXT PRIMARY KEY, offset INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS records_session ON records(session_id, event, offset);
            CREATE INDEX IF NOT EXISTS events_session ON events(session_id, utc);
        """)
        # Add generation markers to databases created by earlier dashboard builds.
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(imports)")}
        for name, sql_type in (("prefix_bytes", "INTEGER"), ("prefix_hash", "TEXT"), ("device", "INTEGER"), ("inode", "INTEGER")):
            if name not in columns:
                self.connection.execute(f"ALTER TABLE imports ADD COLUMN {name} {sql_type}")
        self.connection.commit()
        self.errors = []

    def close(self):
        with self.lock:
            self.connection.close()

    def scan(self):
        """Only complete lines advance the cursor; source bytes are never rewritten."""
        errors = []
        paths = []
        for path in self.log_dir.glob("*.jsonl"):
            try:
                paths.append((path.stat().st_mtime, path))
            except OSError as exc:
                errors.append(f"{path.name}: {type(exc).__name__}")
        for _, path in sorted(paths, key=lambda item: item[0], reverse=True):
            try:
                with self.lock, self.connection:
                    imported = self.connection.execute("SELECT * FROM imports WHERE path=?", (str(path),)).fetchone()
                    cursor = imported["offset"] if imported else 0
                    info = path.stat()
                    with path.open("rb") as source:
                        changed = cursor > info.st_size
                        if imported and imported["prefix_hash"]:
                            digest = hashlib.sha256(source.read(imported["prefix_bytes"])).hexdigest()
                            changed |= digest != imported["prefix_hash"] or (info.st_dev, info.st_ino) != (imported["device"], imported["inode"])
                        if changed:
                            # SQLite is a derived index, never the original evidence.
                            for table in ("records", "events"):
                                self.connection.execute(f"DELETE FROM {table} WHERE session_id=?", (path.stem,))
                            self.connection.execute("DELETE FROM sessions WHERE id=?", (path.stem,))
                            cursor = 0
                        source.seek(cursor)
                        for _ in range(10000):
                            offset = source.tell()
                            line = source.readline(2 * 1024 * 1024)
                            if not line or not line.endswith(b"\n"):
                                break
                            cursor = source.tell()
                            self.connection.execute("SAVEPOINT record_import")
                            try:
                                record = normalize_record(json.loads(line, parse_constant=lambda _: None))
                                self._ingest(path.stem, offset, record)
                            except (ValueError, TypeError, KeyError, sqlite3.Error) as exc:
                                self.connection.execute("ROLLBACK TO record_import")
                                errors.append(f"{path.name}:{offset}: {type(exc).__name__}")
                            finally:
                                self.connection.execute("RELEASE record_import")
                        prefix_bytes = min(cursor, 4096)
                        source.seek(0)
                        prefix_hash = hashlib.sha256(source.read(prefix_bytes)).hexdigest()
                    self.connection.execute("INSERT INTO imports(path,offset,prefix_bytes,prefix_hash,device,inode) VALUES(?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET offset=excluded.offset,prefix_bytes=excluded.prefix_bytes,prefix_hash=excluded.prefix_hash,device=excluded.device,inode=excluded.inode", (str(path), cursor, prefix_bytes, prefix_hash, info.st_dev, info.st_ino))
            except OSError as exc:
                errors.append(f"{path.name}: {type(exc).__name__}")
        self.errors = errors[:20]

    def _event(self, session_id, offset, record, kind):
        self.connection.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?,?)",
            (f"{session_id}:{offset}:{kind}", session_id, record.get("utc"), kind, json.dumps(record, ensure_ascii=False)))

    def _counter_increased(self, session_id, offset, record, previous, key):
        current = count(record.get(key))
        if current is None:
            return False
        known = count(previous.get(key))
        if known is None and previous:
            rows = self.connection.execute("SELECT payload FROM records WHERE session_id=? AND event='status' AND offset<? ORDER BY offset DESC", (session_id, offset))
            for row in rows:
                known = count(json.loads(row[0]).get(key))
                if known is not None:
                    break
        # A missing counter is not a zero baseline or a newly confirmed event.
        return known is not None and current > known

    def _ingest(self, session_id, offset, record):
        event = record.get("event", "unknown")
        self.connection.execute("INSERT OR IGNORE INTO sessions(id,started_at) VALUES(?,?)", (session_id, record.get("utc")))
        inserted = self.connection.execute("INSERT OR IGNORE INTO records VALUES(?,?,?,?,?)",
            (session_id, offset, record.get("utc"), event, json.dumps(record, ensure_ascii=False))).rowcount
        if not inserted:
            return
        if event in ("startup", "session_start"):
            live = record.get("live")
            kind = "camera" if live is True else "video" if live is False else "unknown"
            self.connection.execute("UPDATE sessions SET source=?,source_kind=?,backend=?,lifecycle=?,metadata=? WHERE id=?",
                (str(record.get("source", "")), kind, record.get("backend"), "running" if event == "session_start" else "initializing", json.dumps(record), session_id))
        elif event == "session_end":
            self.connection.execute("UPDATE sessions SET ended_at=?,lifecycle=?,summary=? WHERE id=?",
                (record.get("utc"), "error" if record.get("fault") else "finished", json.dumps(record), session_id))
        elif event == "runtime_fault":
            self.connection.execute("UPDATE sessions SET lifecycle='error' WHERE id=?", (session_id,))
        if event == "status":
            previous = self.connection.execute("SELECT payload FROM records WHERE session_id=? AND event='status' AND offset<? ORDER BY offset DESC LIMIT 1", (session_id, offset)).fetchone()
            previous = json.loads(previous[0]) if previous else {}
            if record.get("state") != previous.get("state"):
                self._event(session_id, offset, record, "state")
            if record.get("alert") and not previous.get("alert"):
                self._event(session_id, offset, record, "alert")
            if self._counter_increased(session_id, offset, record, previous, "yawn_count"):
                self._event(session_id, offset, record, "yawn")
            if self._counter_increased(session_id, offset, record, previous, "blink_total"):
                self._event(session_id, offset, record, "blink")
            if record.get("serial_error") and record.get("serial_error") != previous.get("serial_error"):
                self._event(session_id, offset, record, "serial_fault")
        else:
            self._event(session_id, offset, record, event)

    @staticmethod
    def _session(row):
        if not row:
            return None
        result = dict(row)
        result["summary"] = json.loads(result["summary"])
        result.pop("metadata", None)
        return result

    def sessions(self, limit=50, offset=0, start=None, end=None):
        where, values = [], []
        if start:
            where.append("started_at>=?")
            values.append(start)
        if end:
            where.append("started_at<=?")
            values.append(end)
        clause = " WHERE " + " AND ".join(where) if where else ""
        with self.lock:
            rows = self.connection.execute("SELECT * FROM sessions" + clause + " ORDER BY started_at DESC,id DESC LIMIT ? OFFSET ?", (*values, limit, offset)).fetchall()
        return [self._session(row) for row in rows]

    def session(self, session_id):
        with self.lock:
            return self._session(self.connection.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone())

    def series(self, session_id, limit=1000, offset=0):
        with self.lock:
            session = self.connection.execute("SELECT metadata FROM sessions WHERE id=?", (session_id,)).fetchone()
            metadata = json.loads(session[0]) if session else {}
            rows = self.connection.execute("SELECT offset,payload FROM records WHERE session_id=? AND event='status' ORDER BY offset LIMIT ? OFFSET ?", (session_id, limit, offset)).fetchall()
        return [snapshot(json.loads(row[1]), session_id, row[0], metadata) for row in rows]

    def events(self, session_id, limit=1000, offset=0):
        with self.lock:
            rows = self.connection.execute("SELECT * FROM events WHERE session_id=? ORDER BY utc,id LIMIT ? OFFSET ?", (session_id, limit, offset)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def export_csv(self, session_id):
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["utc", "source_timestamp", "state", "alert", "reasons", "eye_1_closed", "eye_2_closed", "yawn_probability", "quality", "blink_total", "yawn_60s", "fps", "latency_ms"])
        offset = 0
        while rows := self.series(session_id, 1000, offset):
            for row in rows:
                writer.writerow([row["utc"], row["source_timestamp"], row["state"], row["alert"], ",".join(row["reasons"]),
                    row["probabilities"]["eye_1_closed"], row["probabilities"]["eye_2_closed"], row["probabilities"]["yawn"],
                    row["quality"]["image"], row["counts"]["blink_total"], row["counts"]["yawn_60s"], row["performance"]["fps"], row["performance"]["latency_ms"]])
            offset += len(rows)
        return output.getvalue()
