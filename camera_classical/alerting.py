"""Use the common acknowledged/heartbeat implementation."""
from driver_monitor.alerting import NullAlertSink, SerialAlertSink
__all__ = ["NullAlertSink", "SerialAlertSink"]
