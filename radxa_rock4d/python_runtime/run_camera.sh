#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$BASE"
exec "${DRIVER_MONITOR_PYTHON:-python3}" -m driver_monitor run --source "${1:-0}" --backend rknn --headless "${@:2}"
