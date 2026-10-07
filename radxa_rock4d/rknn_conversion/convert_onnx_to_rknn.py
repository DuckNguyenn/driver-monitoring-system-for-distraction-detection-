"""Convert the authoritative ONNX manifest for rk3576, with optional INT8."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from driver_monitor.exporting import convert_main
if __name__ == "__main__":
    convert_main()
