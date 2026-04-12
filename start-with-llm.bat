@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo [2/4] Installing base dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install base dependencies.
  pause
  exit /b 1
)

echo [3/4] Installing LLM / VLM + LLaMA-Factory (large download)...
".venv\Scripts\python.exe" -m pip install -r requirements-llm.txt -r requirements-llm-lf.txt
if errorlevel 1 (
  echo Failed to install LLM dependencies.
  pause
  exit /b 1
)

echo [4/4] Starting app on http://127.0.0.1:7860
echo Tip: weak GPU - keep default perf mode; set TENCLIP_FORCE_CPU=1 to force CPU if OOM.
".venv\Scripts\python.exe" app.py

endlocal
