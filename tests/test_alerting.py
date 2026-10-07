import time
import unittest
from driver_monitor.alerting import SerialLink, SerialAlertSink


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.writes = []
        self.closed = False
        self.reply = b""
    def write(self, value):
        self.writes.append(value)
        self.reply = b"OK ALERT 1\n" if value.startswith(b"ALERT 1") else b"OK ALERT 0\n"
    def readline(self):
        value, self.reply = self.reply, b""
        return value
    def close(self):
        self.closed = True


class AlertTests(unittest.TestCase):
    def test_exact_command_ack_and_clean_shutdown(self):
        link = SerialLink("fake", serial_factory=FakeSerial)
        link.send(True, ("eyes_closed_too_long",))
        link.send(False)
        serial = link.serial
        self.assertEqual(serial.writes, [b"ALERT 1 eyes_closed_too_long\n", b"ALERT 0\n"])
        link.close()
        self.assertTrue(serial.closed)

    def test_missing_ack_is_reported(self):
        class MissingAck(FakeSerial):
            def readline(self):
                time.sleep(.01)
                return b""
        link = SerialLink("fake", serial_factory=MissingAck)
        with self.assertRaises(TimeoutError):
            link.send(True)
        link.close()

    def test_heartbeat_and_inference_stall_force_off(self):
        serial = FakeSerial()
        sink = SerialAlertSink("fake", heartbeat=.10, freshness=.20, serial_factory=lambda *a, **k: serial)
        sink.set_alert(True, ("eyes_closed_too_long",))
        time.sleep(.12)
        sink.set_alert(True, ("eyes_closed_too_long",))
        time.sleep(.12)
        sink.set_alert(True, ("eyes_closed_too_long",))
        time.sleep(.35)
        sink.close()
        self.assertGreaterEqual(sum(w.startswith(b"ALERT 1") for w in serial.writes), 2)
        self.assertEqual(serial.writes[-1], b"ALERT 0\n")
        self.assertTrue(serial.closed)

    def test_transport_failure_reconnects(self):
        first = FakeSerial()
        def broken(_):
            raise OSError("unplugged")
        first.write = broken
        second = FakeSerial()
        transports = iter((first, second))
        sink = SerialAlertSink("fake", serial_factory=lambda *a, **k: next(transports))
        time.sleep(1.2)
        sink.close()
        self.assertTrue(first.closed)
        self.assertIn(b"ALERT 0\n", second.writes)

    def test_blocked_connection_does_not_send_a_stale_alarm(self):
        serial = FakeSerial()
        def slow_open(*args, **kwargs):
            time.sleep(.25)
            return serial
        sink = SerialAlertSink("fake", freshness=.10, serial_factory=slow_open)
        sink.set_alert(True, ("eyes_closed_too_long",))
        time.sleep(.35)
        sink.close()
        self.assertTrue(serial.writes)
        self.assertTrue(all(value == b"ALERT 0\n" for value in serial.writes))

    def test_shutdown_waits_for_boot_and_sends_off(self):
        serial = FakeSerial()
        def slow_open(*args, **kwargs):
            time.sleep(.25)
            return serial
        sink = SerialAlertSink("fake", serial_factory=slow_open)
        time.sleep(.03)
        sink.close()
        self.assertEqual(serial.writes[-1], b"ALERT 0\n")
        self.assertTrue(serial.closed)
