"""Acknowledged ESP32 commands with independent heartbeat and freshness cutoff."""
import threading
import time


class NullAlertSink:
    last_error = None
    def set_alert(self, active, reasons=()):
        pass
    def close(self):
        pass


class SerialLink:
    """A single acknowledged transaction; injectable serial transport for tests."""
    def __init__(self, port, baudrate=115200, serial_factory=None):
        self.port, self.baudrate = port, baudrate
        self.factory = serial_factory
        self.serial = None

    def connect(self):
        if self.serial is None:
            if self.factory is None:
                import serial
                self.factory = serial.Serial
            self.serial = self.factory(self.port, self.baudrate, timeout=0.05, write_timeout=0.2)
            if self.factory.__module__.startswith("serial"):
                # Opening a USB serial device can reset ESP32 through DTR.
                time.sleep(2.0)

    def send(self, active, reasons=()):
        self.connect()
        # An ACK left over from an earlier heartbeat must not acknowledge this command.
        if hasattr(self.serial, "reset_input_buffer"):
            self.serial.reset_input_buffer()
        suffix = ",".join(r for r in reasons if r.replace("_", "").isalnum())
        command = f"ALERT 1 {suffix}".rstrip() if active else "ALERT 0"
        self.serial.write((command + "\n").encode("ascii"))
        expected = b"OK ALERT 1" if active else b"OK ALERT 0"
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            response = self.serial.readline().strip()
            if response == expected:
                return
            if response.startswith(b"ERR"):
                raise OSError(response.decode("ascii", errors="replace"))
        raise TimeoutError(f"ESP32 did not acknowledge {command}")

    def close(self):
        if self.serial is not None:
            self.serial.close()
            self.serial = None


class SerialAlertSink:
    """Inference cannot block serial I/O or leave an alert alive while stalled."""
    def __init__(self, port, baudrate=115200, heartbeat=0.5, freshness=0.25, serial_factory=None):
        if serial_factory is None:
            import serial
            serial_factory = serial.Serial
        self.link = SerialLink(port, baudrate, serial_factory)
        self.heartbeat, self.freshness = heartbeat, freshness
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._desired = (False, ())
        self._updated = float("-inf")
        self.last_error = None
        self.last_ack = None
        self._thread = threading.Thread(target=self._run, name="esp32-heartbeat", daemon=True)
        self._thread.start()

    def set_alert(self, active, reasons=()):
        with self._lock:
            changed = self._desired != (bool(active), tuple(reasons))
            self._desired = bool(active), tuple(reasons)
            self._updated = time.monotonic()
        if changed:
            self._wake.set()

    def _run(self):
        sent = None
        next_send = 0.0
        retry_at = 0.0
        try:
            while not self._stop.is_set():
                now = time.monotonic()
                with self._lock:
                    desired = self._desired if now - self._updated <= self.freshness else (False, ())
                if now >= retry_at and (sent != desired or now >= next_send):
                    try:
                        self.link.connect()
                        # Connecting may wait for ESP32 to boot. Recheck freshness afterwards.
                        now = time.monotonic()
                        with self._lock:
                            desired = self._desired if now - self._updated <= self.freshness else (False, ())
                        if self._stop.is_set():
                            break
                        self.link.send(*desired)
                        sent = desired
                        self.last_error = None
                        self.last_ack = time.monotonic()
                        next_send = now + self.heartbeat
                    except (OSError, TimeoutError) as exc:
                        self.last_error = f"{type(exc).__name__}: {exc}"
                        self.link.close()
                        sent = None
                        retry_at = now + 1.0
                self._wake.wait(0.05)
                self._wake.clear()
        finally:
            if self.link.serial is not None:
                try:
                    self.link.send(False)
                except (OSError, TimeoutError):
                    pass
            self.link.close()

    def close(self):
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=3.0)
