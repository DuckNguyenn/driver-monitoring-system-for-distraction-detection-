"""Compatibility interface for the PC Face Mesh comparison pipeline."""
from driver_monitor.core import Monitor, MonitorConfig, Observation, Status

DrowsinessConfig = MonitorConfig
DrowsinessStatus = Status

class DrowsinessMonitor(Monitor):
    def update(self, timestamp, eye_closed, yawn_probability=0.0):
        eye = None if eye_closed is None else {"Closed": float(eye_closed), "Open": float(not eye_closed)}
        mouth = None if yawn_probability is None else {"yawn": yawn_probability, "no_yawn": 1 - yawn_probability}
        return super().update(Observation(timestamp, eye, eye, mouth))
