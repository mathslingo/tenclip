@echo off
setlocal
cd /d "%~dp0"

REM 优先使用已配置的 conda（与 setup-conda-env 一致）
if not defined CONDA_ROOT set "CONDA_ROOT=C:\Users\baozi\anaconda3"
set "CONDA_EXE=%CONDA_ROOT%\Scripts\conda.exe"

if exist "%CONDA_EXE%" (
  echo Using conda env tenclip...
  "%CONDA_EXE%" run -n tenclip python app.py
  exit /b %ERRORLEVEL%
)

echo No conda at "%CONDA_EXE%", using python on PATH...
python app.py
exit /b %ERRORLEVEL%
