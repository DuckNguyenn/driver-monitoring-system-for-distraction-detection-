@echo off
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Create .venv and install requirements-host.txt first.
  exit /b 1
)
".venv\Scripts\python.exe" -m driver_monitor run --source 0 --backend onnx --config configs/camera_pc.yaml --display %*
