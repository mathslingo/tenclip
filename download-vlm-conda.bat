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

echo 默认从 ModelScope 下载（可用 set TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface 改为 HF）
"%CONDA_EXE%" run -n tenclip python scripts\download_vlm_weights.py
if errorlevel 1 (
  echo 失败。请确认已运行 setup-conda-env.bat
  pause
  exit /b 1
)
echo.
echo 下载完成。启动: start-conda-llm.bat
pause
endlocal
