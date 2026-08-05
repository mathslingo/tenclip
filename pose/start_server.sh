#!/bin/bash
# MMPose 实时姿态估计服务启动脚本

set -e

echo "=================================="
echo "MMPose 姿态估计服务启动脚本"
echo "=================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误：未找到 python3"
    exit 1
fi

# 检查依赖
echo "检查依赖..."

check_package() {
    python3 -c "import $1" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "✗ 缺少依赖: $1"
        return 1
    else
        echo "✓ $1"
        return 0
    fi
}

missing_deps=0

# 基础依赖
for pkg in flask cv2 numpy PIL; do
    check_package $pkg || missing_deps=$((missing_deps + 1))
done

# 检查 MMPose（可选）
check_package mmpose || echo "  提示：未安装 MMPose，将使用 MediaPipe"

# 检查 MediaPipe（备选）
check_package mediapipe || echo "  提示：未安装 MediaPipe"

if [ $missing_deps -gt 0 ]; then
    echo ""
    echo "缺少必要依赖，正在安装..."
    echo ""
    
    read -p "是否自动安装缺失的依赖？(y/n) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "安装基础依赖..."
        pip install flask flask-cors opencv-python numpy pillow
        
        echo ""
        read -p "是否安装 MMPose（推荐，但需要较长时间）？(y/n) " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "安装 MMPose..."
            pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
            pip install -U openmim
            mim install mmengine
            mim install mmcv
            mim install mmdet
            mim install mmpose
        else
            echo "安装 MediaPipe（轻量级替代）..."
            pip install mediapipe
        fi
    else
        echo "跳过依赖安装"
        exit 1
    fi
fi

echo ""
echo "=================================="
echo "启动服务..."
echo "=================================="

# 设置环境变量
export FLASK_ENV=production
export PORT=5000

# 启动服务
python3 pose_server.py
