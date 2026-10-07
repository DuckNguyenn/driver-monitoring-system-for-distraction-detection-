"""Run the common export and manifest generator from this legacy entrypoint."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from driver_monitor.exporting import export_main
if __name__ == "__main__":
    export_main()
