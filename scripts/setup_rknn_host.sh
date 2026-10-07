#!/usr/bin/env bash
# Private Linux x86_64 conversion environment; no system Python or global packages changed.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
if [[ "${1:-}" == --verify-only ]]; then
  export MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib-rknn"
  export PYTHONUNBUFFERED=1
  exec .venv-rknn/bin/python tools/verify_rknn_sim.py
fi
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This bootstrap is for a Linux/WSL x86_64 conversion host.' >&2
  exit 2
fi
export UV_CACHE_DIR="$PROJECT_DIR/.cache/uv-rknn/cache"
export UV_PYTHON_INSTALL_DIR="$PROJECT_DIR/.cache/python-rknn"
export UV_PYTHON_BIN_DIR="$PROJECT_DIR/.cache/python-bin-rknn"
export UV_LINK_MODE=copy
export UV_HTTP_TIMEOUT=120
export MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib-rknn"
export PYTHONUNBUFFERED=1
mkdir -p "$PROJECT_DIR/.cache/uv-rknn" "$MPLCONFIGDIR"
UV_BIN="$PROJECT_DIR/.cache/uv-rknn/uv"
if [[ ! -x "$UV_BIN" ]]; then
  UV_ARCHIVE="$PROJECT_DIR/.cache/uv-rknn/uv-x86_64-unknown-linux-gnu.tar.gz"
  UV_URL='https://github.com/astral-sh/uv/releases/download/0.9.16/uv-x86_64-unknown-linux-gnu.tar.gz'
  curl --fail --location --retry 2 --connect-timeout 20 --max-time 180 "$UV_URL" -o "$UV_ARCHIVE"
  curl --fail --location --retry 2 --connect-timeout 20 --max-time 60 "$UV_URL.sha256" -o "$UV_ARCHIVE.sha256"
  UV_EXPECTED_SHA="$(awk '{print $1}' "$UV_ARCHIVE.sha256")"
  UV_ACTUAL_SHA="$(sha256sum "$UV_ARCHIVE" | awk '{print $1}')"
  if [[ ! "$UV_EXPECTED_SHA" =~ ^[0-9a-f]{64}$ || "$UV_EXPECTED_SHA" != "$UV_ACTUAL_SHA" ]]; then
    echo 'uv archive checksum mismatch' >&2
    exit 1
  fi
  tar -xzf "$UV_ARCHIVE" -C "$PROJECT_DIR/.cache/uv-rknn" --strip-components=1 uv-x86_64-unknown-linux-gnu/uv
fi
"$UV_BIN" python install 3.12.10
if [[ ! -x .venv-rknn/bin/python ]]; then
  "$UV_BIN" venv --python 3.12.10 --managed-python .venv-rknn
fi
.venv-rknn/bin/python -c "import sys; assert sys.version_info[:3] == (3,12,10), 'Use the private Python 3.12.10 conversion venv'"
"$UV_BIN" pip install --python .venv-rknn/bin/python 'torch==2.4.0' --index-url https://download.pytorch.org/whl/cpu
"$UV_BIN" pip install --python .venv-rknn/bin/python -r radxa_rock4d/rknn_conversion/requirements-host.txt
"$UV_BIN" pip check --python .venv-rknn/bin/python
"$UV_BIN" pip freeze --python .venv-rknn/bin/python > requirements-rknn-linux.lock.txt
.venv-rknn/bin/python -m driver_monitor convert --manifest models/manifest.json
