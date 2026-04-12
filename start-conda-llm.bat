@echo off
setlocal
cd /d "%~dp0"

if not defined CONDA_ROOT set "CONDA_ROOT=C:\Users\baozi\anaconda3"
set "CONDA_EXE=%CONDA_ROOT%\Scripts\conda.exe"

if not exist "%CONDA_EXE%" (
  echo [错误] 未找到 "%CONDA_EXE%"，请设置 CONDA_ROOT。
  pause
  exit /b 1
)

echo 使用 "%CONDA_EXE%" 环境 tenclip 启动 http://127.0.0.1:7860
"%CONDA_EXE%" run -n tenclip python app.py
if errorlevel 1 (
  echo 若提示环境不存在，请先运行 setup-conda-env.bat
  pause
  exit /b 1
)
endlocal
