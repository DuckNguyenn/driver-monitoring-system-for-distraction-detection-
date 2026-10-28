"""LAN monitoring API. Its process never owns the camera or buzzer."""
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import queue
import secrets
import signal
import socket
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import ROOT
from .dashboard_data import utc_now
from .dashboard_history import HistoryIndex
from .dashboard_transport import DashboardPublisher


class LiveHub:
    def __init__(self, statuses, frames, demand, clock=time.monotonic):
        self.statuses, self.frames, self.demand, self.clock = statuses, frames, demand, clock
        self.latest = self.preview = None
        self.received = 0.
        self.preview_changed = asyncio.Event()

    def drain(self):
        for channel, name in ((self.statuses, "latest"), (self.frames, "preview")):
            for _ in range(32):
                try:
                    value = channel.get_nowait()
                except queue.Empty:
                    break
                if name == "latest":
                    value = dict(value)
                    self.received = value.pop("_published_at", self.clock())
                setattr(self, name, value)
                if name == "preview":
                    self.preview_changed.set()

    def current(self):
        if self.latest is None:
            return None
        age = max(0., self.clock() - self.received)
        return dict(self.latest, age_ms=round(age * 1000, 1),
                    connected=age <= 2 and self.latest["lifecycle"] == "running")

    def frame(self):
        self.demand.value = self.clock() + 1.0
        current = self.current()
        if not current or not current["connected"] or self.preview is None or self.clock() - self.preview["time"] > 2:
            return None
        return self.preview


def connection_token(log_dir):
    override = os.environ.get("DRIVER_MONITOR_TOKEN")
    if override:
        if len(override) < 16:
            raise ValueError("DRIVER_MONITOR_TOKEN must contain at least 16 characters")
        return override
    path = Path(log_dir) / ".dashboard-token"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as target:
            target.write(secrets.token_urlsafe(32))
        path.chmod(0o600)
    except FileExistsError:
        pass
    token = path.read_text(encoding="utf-8").strip()
    if len(token) < 16:
        raise ValueError(f"Invalid connection code file: {path}")
    return token


def create_app(log_dir, token, hub, web_dir=None):
    history = HistoryIndex(Path(log_dir) / "dashboard.sqlite3", log_dir)

    async def drain():
        while True:
            hub.drain()
            await asyncio.sleep(.03)

    async def index_history():
        while True:
            work = asyncio.create_task(asyncio.to_thread(history.scan))
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                await work
                raise
            except Exception as exc:
                history.errors = [f"History indexing: {type(exc).__name__}"]
            await asyncio.sleep(1)

    @asynccontextmanager
    async def lifespan(_):
        tasks = []
        try:
            await asyncio.to_thread(history.scan)
            tasks = [asyncio.create_task(drain()), asyncio.create_task(index_history())]
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            # Wait for any in-flight indexing thread before closing SQLite.
            await asyncio.to_thread(history.close)

    app = FastAPI(title="Driver Monitor LAN", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(?:localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?::\d{1,5})?",
                       allow_methods=["GET", "HEAD"], allow_headers=["Authorization"], expose_headers=["X-Frame-Sequence", "X-Frame-Age-Ms"])
    app.state.history, app.state.hub = history, hub

    def check_token(value):
        return isinstance(value, str) and secrets.compare_digest(value.encode(), token.encode())

    def authorize(authorization: str | None = Header(default=None)):
        if authorization is None or not authorization.startswith("Bearer ") or not check_token(authorization[7:]):
            raise HTTPException(401, "Mã kết nối không hợp lệ", headers={"WWW-Authenticate": "Bearer"})

    def require_session(session_id):
        row = history.session(session_id)
        if row is None:
            raise HTTPException(404, "Không tìm thấy phiên")
        return row

    def page(rows, offset, limit):
        return {"items": rows, "next_offset": offset + len(rows) if len(rows) == limit else None}

    guarded = [Depends(authorize)]

    @app.get("/api/v1/status", dependencies=guarded)
    def status():
        return hub.current()

    @app.get("/api/v1/health", dependencies=guarded)
    def health():
        return {"utc": utc_now(), "history_errors": history.errors, "read_only": True}

    @app.get("/api/v1/sessions", dependencies=guarded)
    def sessions(limit: int = Query(50, ge=1, le=1000), offset: int = Query(0, ge=0),
                 start: datetime | None = None, end: datetime | None = None):
        def utc(value):
            if value is None:
                return None
            if value.tzinfo is None:
                raise HTTPException(422, "Thời gian lọc cần múi giờ")
            return value.astimezone(timezone.utc).isoformat()
        return page(history.sessions(limit, offset, utc(start), utc(end)), offset, limit)

    @app.get("/api/v1/sessions/{session_id}", dependencies=guarded)
    def session(session_id: str):
        return require_session(session_id)

    @app.get("/api/v1/sessions/{session_id}/series", dependencies=guarded)
    def series(session_id: str, limit: int = Query(1000, ge=1, le=1000), offset: int = Query(0, ge=0)):
        require_session(session_id)
        return page(history.series(session_id, limit, offset), offset, limit)

    @app.get("/api/v1/sessions/{session_id}/events", dependencies=guarded)
    def events(session_id: str, limit: int = Query(1000, ge=1, le=1000), offset: int = Query(0, ge=0)):
        require_session(session_id)
        return page(history.events(session_id, limit, offset), offset, limit)

    @app.get("/api/v1/sessions/{session_id}/export.csv", dependencies=guarded)
    def export(session_id: str):
        require_session(session_id)
        return Response("\ufeff" + history.export_csv(session_id), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="driver-monitor-session.csv"', "Cache-Control": "no-store"})

    @app.api_route("/api/v1/frame.jpg", methods=["GET", "HEAD"], dependencies=guarded)
    async def frame(request: Request, after: str | None = Query(None, max_length=32)):
        deadline = time.monotonic() + .25
        while True:
            hub.preview_changed.clear()
            value = hub.frame()
            if value is None:
                raise HTTPException(503, "Camera chưa có ảnh mới", headers={"Cache-Control": "no-store"})
            headers = {"Cache-Control":"no-store", "X-Frame-Sequence":str(value["sequence"]),
                       "X-Frame-Age-Ms":str(round(max(0., hub.clock()-value["time"])*1000,1))}
            if after is None or str(value["sequence"]) != after:
                return Response(value["jpeg"] if request.method == "GET" else b"", media_type="image/jpeg", headers=headers)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return Response(status_code=204, headers=headers)
            try:
                await asyncio.wait_for(hub.preview_changed.wait(), remaining)
            except asyncio.TimeoutError:
                return Response(status_code=204, headers=headers)

    @app.websocket("/api/v1/ws")
    async def websocket(ws: WebSocket):
        await ws.accept()
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=5)
            if len(raw) > 1024:
                await ws.close(1008)
                return
            message = json.loads(raw)
            if not isinstance(message, dict) or message.get("type") != "auth" or not check_token(message.get("token")):
                await ws.close(1008)
                return
            while True:
                # No per-client queue: a slow client always reads the current value.
                await asyncio.wait_for(ws.send_json({"type": "snapshot", "snapshot": hub.current(), "server_utc": utc_now()}), 2)
                await asyncio.sleep(.2)
        except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, RuntimeError):
            with suppress(RuntimeError, WebSocketDisconnect):
                await ws.close(1008)

    static = Path(web_dir) if web_dir else ROOT / "frontend/web/dist"
    if (static / "assets").exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/")
    def index():
        if (static / "index.html").exists():
            return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})
        return Response("Dashboard chưa được build. Chạy npm run build:web tại thư mục dự án.", media_type="text/plain")

    return app


def _worker(config, source, duration, statuses, frames, demand, stop_event, preview_fps):
    from .runtime import run
    publisher = DashboardPublisher(statuses, frames, demand, preview_fps=preview_fps)
    try:
        run(config, source, duration, publisher, stop_event)
    except Exception:
        pass  # runtime persisted/published the failure; API remains available for history
    finally:
        publisher.close()
        if stop_event.is_set():
            # The API may already have stopped draining pipes during shutdown.
            statuses.cancel_join_thread()
            frames.cancel_join_thread()


def stop_worker(process, grace=8., terminate_grace=2., kill_grace=2.):
    process.join(timeout=grace)
    if process.is_alive():
        process.terminate()
        process.join(timeout=terminate_grace)
    if process.is_alive():
        # SIGTERM handlers cannot interrupt a hung native call on Linux.
        process.kill()
        process.join(timeout=kill_grace)


def serve(config, source="0", duration=0., host="0.0.0.0", port=8765, preview_fps=15):
    # Reserve the actual listener before opening SQLite, camera or serial. Keep it
    # open through startup so another process cannot take the port in between.
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        listener = socket.create_server((host, port), family=family)
    except OSError as exc:
        if exc.errno in (errno.EADDRINUSE, 10048):
            raise RuntimeError(
                f"Cong {port} dang duoc su dung. Dung phien serve cu bang Ctrl+C "
                "trong terminal da chay no, roi chay lai. "
                "Chi chay mot runtime voi cung camera/ESP32."
            ) from exc
        raise
    with listener:
        _serve_bound(config, source, duration, host, port, preview_fps, listener)


def _serve_bound(config, source, duration, host, port, preview_fps, listener):
    import multiprocessing as mp
    import uvicorn
    context = mp.get_context("spawn")
    statuses, frames = context.Queue(4), context.Queue(1)
    demand, stop_event = context.Value("d", 0., lock=False), context.Event()
    token = connection_token(config.log_dir)
    hub = LiveHub(statuses, frames, demand)
    app = create_app(config.log_dir, token, hub)
    process = context.Process(target=_worker, args=(config, source, duration, statuses, frames, demand, stop_event, preview_fps), name="driver-monitor-inference")
    address = host
    if host == "0.0.0.0":
        try:
            # UDP connect only selects the OS route; no datagram is sent.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("192.0.2.1", 9))
                address = probe.getsockname()[0]
        except OSError:
            address = "<IPv4-Wi-Fi-PC>"
    print(f"Web tren PC: http://127.0.0.1:{port}\nWeb/app cung Wi-Fi: http://{address}:{port}"
          f"\nPreview: toi da {preview_fps} FPS, giao dien Driver monitor\nMa ket noi: {token}", flush=True)
    class ApiServer(uvicorn.Server):
        def handle_exit(self, sig, frame):
            stop_event.set()
            super().handle_exit(sig, frame)
    server = ApiServer(uvicorn.Config(app, host=host, port=port, access_log=False, ws_max_size=2048, ws_max_queue=2))
    old_handlers = {}
    def shutdown(*_):
        stop_event.set()
        server.should_exit = True
    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        signals.append(signal.SIGBREAK)
    for name in signals:
        old_handlers[name] = signal.signal(name, shutdown)
    started = False
    try:
        process.start()
        started = True
        server.run(sockets=[listener])
    finally:
        stop_event.set()
        if started:
            stop_worker(process)
        for channel in (statuses, frames):
            channel.cancel_join_thread()
            channel.close()
        for name, handler in old_handlers.items():
            signal.signal(name, handler)
