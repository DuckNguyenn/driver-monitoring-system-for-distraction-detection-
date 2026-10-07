"""Compatibility imports for the shared serial implementation."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from driver_monitor.alerting import NullAlertSink, SerialAlertSink
