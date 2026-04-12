@echo off
setlocal
cd /d "%~dp0"

if not defined CONDA_ROOT set "CONDA_ROOT=C:\Users\baozi\anaconda3"
set "CONDA_EXE=%CONDA_ROOT%\Scripts\conda.exe"

if not exist "%CONDA_EXE%" (
  echo [错误] 未找到 "%CONDA_EXE%"
  echo 请安装 Anaconda 或设置环境变量 CONDA_ROOT 为你的 conda 安装目录。
  pause
  exit /b 1
)

echo 使用 conda: "%CONDA_EXE%"
echo [1/2] 创建或更新环境 tenclip（environment.yml，含 LLaMA-Factory + ModelScope）...
"%CONDA_EXE%" env create -f environment.yml
if errorlevel 1 (
  echo 环境可能已存在，正在 update --prune ...
  "%CONDA_EXE%" env update -f environment.yml --prune
  if errorlevel 1 (
    echo 失败。可手动: "%CONDA_EXE%" env create -f environment.yml
    pause
    exit /b 1
  )
)

echo.
echo [2/2] 完成。
echo 可选: 双击 download-vlm-conda.bat 从 ModelScope 预下载权重
echo 启动: 双击 start-conda-llm.bat
echo.
pause
endlocal
