#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="${1:-onnx}"
if [[ "$BACKEND" != onnx && "$BACKEND" != rknn ]]; then
  echo "Usage: bash scripts/setup_radxa.sh [onnx|rknn]" >&2
  exit 2
fi
cd "$PROJECT_DIR"
python3 - <<'PY'
from pathlib import Path
import platform,sys
if platform.machine().lower() not in ('aarch64','arm64'):
    raise SystemExit('Radxa setup requires ARM64 Linux')
if not (3,10) <= sys.version_info[:2] <= (3,12):
    raise SystemExit('Use Python 3.10, 3.11 or 3.12 for the pinned SDK')
board=Path('/proc/device-tree/compatible').read_bytes()
if b'rk3576' not in board:
    raise SystemExit('This package targets ROCK 4D / RK3576')
print('RK3576 detected')
PY
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-runtime.txt
if [[ "$BACKEND" == rknn ]]; then
  .venv/bin/python -m pip install rknn-toolkit-lite2==2.3.2
else
  .venv/bin/python -m pip install onnxruntime==1.20.1
fi
.venv/bin/python -m driver_monitor preflight --backend "$BACKEND" --output reports/radxa_preflight.json
.venv/bin/python - "$BACKEND" <<'PY'
import sys,numpy as np
from driver_monitor.config import load_config
from driver_monitor.models import Classifier
c=load_config('configs/driver_monitor.yaml',backend=sys.argv[1])
for name in ('eye','yawn'):
    model=Classifier(c.manifest,name,c.backend)
    try: print(name,model.predict(np.zeros((224,224,3),np.uint8)))
    finally: model.close()
PY
echo "Inference smoke passed. Configure camera ROI and ESP32 port before enabling the service."
