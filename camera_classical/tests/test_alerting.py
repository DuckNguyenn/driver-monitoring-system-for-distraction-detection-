import unittest
from camera_classical.alerting import SerialAlertSink
from driver_monitor.alerting import SerialAlertSink as SharedSerialAlertSink
class CompatibilityTests(unittest.TestCase):
    def test_pc_uses_same_serial_adapter(self):
        self.assertIs(SerialAlertSink, SharedSerialAlertSink)
