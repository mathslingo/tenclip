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
set "USE_MODELSCOPE_HUB=1"

echo Starting LLaMA-Factory chat with %TENCLIP_LLM_MODEL% ...
"%CONDA_EXE%" run -n tenclip llamafactory-cli chat configs\inference\deepseek_r1_7b.yaml model_name_or_path=%TENCLIP_LLM_MODEL%
if errorlevel 1 (
  echo Startup failed. If you have downloaded the model to a local folder, run:
  echo   set TENCLIP_LLM_MODEL=YOUR_LOCAL_MODEL_PATH
  echo Then start this script again.
  pause
  exit /b 1
)

endlocal
