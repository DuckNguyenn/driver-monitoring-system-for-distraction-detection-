"""Compatibility imports; there is one temporal implementation."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from camera_classical.drowsiness import DrowsinessConfig, DrowsinessMonitor, DrowsinessStatus
