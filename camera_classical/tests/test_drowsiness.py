import unittest
from camera_classical.drowsiness import DrowsinessMonitor
class CompatibilityTests(unittest.TestCase):
    def test_pc_comparison_uses_shared_time_policy(self):
        monitor = DrowsinessMonitor()
        for i in range(17):
            status = monitor.update(i / 10, True, 0.)
        self.assertTrue(status.alert)
        status = monitor.update(1.7, None, None)
        self.assertIsNone(status.eye_closed)
        self.assertFalse(status.alert)
