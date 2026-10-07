@echo off
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: run_video.cmd "path\video.mp4"
  exit /b 1
)
".venv\Scripts\python.exe" -m driver_monitor run --source "%~1" --backend onnx --display --realtime
