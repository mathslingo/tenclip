@echo off
setlocal
cd /d "%~dp0"

if not defined CONDA_ROOT set "CONDA_ROOT=C:\Users\baozi\anaconda3"
set "CONDA_EXE=%CONDA_ROOT%\Scripts\conda.exe"

if not exist "%CONDA_EXE%" (
  echo [ERROR] Conda not found: "%CONDA_EXE%"
  echo Please install Anaconda or set CONDA_ROOT first.
  pause
  exit /b 1
)

if not defined TENCLIP_LLM_MODEL set "TENCLIP_LLM_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
if not defined TENCLIP_LLM_MODEL_DOWNLOAD_SOURCE set "TENCLIP_LLM_MODEL_DOWNLOAD_SOURCE=modelscope"

echo Downloading %TENCLIP_LLM_MODEL% from %TENCLIP_LLM_MODEL_DOWNLOAD_SOURCE% ...
"%CONDA_EXE%" run -n tenclip python scripts\download_llm_weights.py
if errorlevel 1 (
  echo Download failed. Make sure the tenclip environment is ready first.
  pause
  exit /b 1
)

echo.
echo Finished. You can now run start-llamafactory-deepseek-chat.bat
pause
endlocal
