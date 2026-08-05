# MMPose 实时姿态估计服务启动脚本 (Windows)

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "MMPose 姿态估计服务启动脚本" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd
        break
    }
}

if (-not $pythonCmd) {
    Write-Host "错误：未找到 Python" -ForegroundColor Red
    Write-Host "请安装 Python 3.8+ : https://www.python.org/downloads/" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "✓ 找到 Python: $pythonCmd" -ForegroundColor Green

# 检查依赖
Write-Host ""
Write-Host "检查依赖..." -ForegroundColor Cyan

$missingDeps = 0

function Test-PythonPackage {
    param($packageName)
    
    $result = & $pythonCmd -c "import $packageName" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $packageName" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  ✗ 缺少: $packageName" -ForegroundColor Red
        return $false
    }
}

# 检查基础依赖
$packages = @("flask", "cv2", "numpy", "PIL")
foreach ($pkg in $packages) {
    if (-not (Test-PythonPackage $pkg)) {
        $missingDeps++
    }
}

# 检查 MMPose（可选）
if (-not (Test-PythonPackage "mmpose")) {
    Write-Host "  提示：未安装 MMPose，将使用 MediaPipe" -ForegroundColor Yellow
}

# 检查 MediaPipe（备选）
if (-not (Test-PythonPackage "mediapipe")) {
    Write-Host "  提示：未安装 MediaPipe" -ForegroundColor Yellow
}

if ($missingDeps -gt 0) {
    Write-Host ""
    Write-Host "缺少必要依赖" -ForegroundColor Yellow
    
    $install = Read-Host "是否自动安装缺失的依赖？(y/n)"
    
    if ($install -eq "y" -or $install -eq "Y") {
        Write-Host ""
        Write-Host "安装基础依赖..." -ForegroundColor Cyan
        & $pythonCmd -m pip install flask flask-cors opencv-python numpy pillow
        
        Write-Host ""
        $installMMPose = Read-Host "是否安装 MMPose（推荐，但需要较长时间）？(y/n)"
        
        if ($installMMPose -eq "y" -or $installMMPose -eq "Y") {
            Write-Host "安装 MMPose..." -ForegroundColor Cyan
            & $pythonCmd -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
            & $pythonCmd -m pip install -U openmim
            & $pythonCmd -m mim install mmengine
            & $pythonCmd -m mim install mmcv
            & $pythonCmd -m mim install mmdet
            & $pythonCmd -m mim install mmpose
        } else {
            Write-Host "安装 MediaPipe（轻量级替代）..." -ForegroundColor Cyan
            & $pythonCmd -m pip install mediapipe
        }
    } else {
        Write-Host "跳过依赖安装" -ForegroundColor Yellow
        pause
        exit 1
    }
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "启动服务..." -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# 设置环境变量
$env:FLASK_ENV = "production"
$env:PORT = "5000"

# 启动服务
& $pythonCmd pose_server.py
