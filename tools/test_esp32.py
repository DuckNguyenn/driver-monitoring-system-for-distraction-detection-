"""Bench verification of ESP32 ACK latency. Does not flash the device."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver_monitor.alerting import SerialLink

parser = argparse.ArgumentParser()
parser.add_argument("--port", required=True)
args = parser.parse_args()
link = SerialLink(args.port)
try:
    link.send(False)
    start = time.monotonic()
    link.send(True, ("bench_test",))
    print(f"ALERT 1 ACK latency: {(time.monotonic()-start)*1000:.1f} ms")
    time.sleep(.5)
    link.send(False)
    print("ACK test passed. Physical buzzer and unplug/2s timeout still require observation.")
finally:
    try: link.send(False)
    finally: link.close()
