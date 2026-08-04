#!/bin/bash
# MMPose GPU 加速启动脚本（针对 conda tenclip 环境）

set -e

echo "=========================================="
echo "MMPose GPU 姿态估计服务"
echo "环境：conda tenclip + NVIDIA 3060"
echo "=========================================="
echo ""

# 激活 conda 环境
echo "激活 conda tenclip 环境..."
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate tenclip

# 验证 GPU
echo ""
echo "检查 GPU 状态..."
python3 << 'EOF'
import torch
import sys

print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA 版本: {torch.version.cuda}")
    print(f"GPU 设备: {torch.cuda.get_device_name(0)}")
    print(f"GPU 显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    print("✓ GPU 检测成功")
else:
    print("✗ CUDA 不可用，将使用 CPU")
    print("请检查：")
    print("  1. NVIDIA 驱动是否正确安装")
    print("  2. PyTorch 是否为 CUDA 版本")
    print("  3. WSL 是否启用了 GPU 支持")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    read -p "GPU 检测失败，是否继续使用 CPU？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查依赖
echo ""
echo "检查依赖..."

check_package() {
    python3 -c "import $1" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  ✓ $1"
        return 0
    else
        echo "  ✗ $1 (需要安装)"
        return 1
    fi
}

missing=0
for pkg in flask cv2 numpy PIL; do
    check_package $pkg || missing=$((missing + 1))
done

# 检查 MMPose（重要）
if check_package mmpose; then
    echo ""
    echo "✓ 检测到 MMPose，将使用高性能 GPU 推理"
    USE_MMPOSE=true
else
    echo ""
    echo "提示：未检测到 MMPose"
    read -p "是否安装 MMPose？(推荐，y/n) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "安装 MMPose（这可能需要几分钟）..."
        
        # 确保 PyTorch 是 CUDA 版本
        echo "验证 PyTorch CUDA 支持..."
        python3 -c "import torch; assert torch.cuda.is_available(), 'PyTorch 不支持 CUDA'"
        
        # 安装 MMPose
        echo "安装 OpenMMLab 工具..."
        pip install -U openmim
        
        echo "安装 MMEngine..."
        mim install mmengine
        
        echo "安装 MMCV..."
        mim install "mmcv>=2.0.0"
        
        echo "安装 MMDetection..."
        mim install "mmdet>=3.0.0"
        
        echo "安装 MMPose..."
        mim install "mmpose>=1.0.0"
        
        echo ""
        echo "✓ MMPose 安装完成"
        USE_MMPOSE=true
    else
        echo "将使用 MediaPipe（备选方案）"
        check_package mediapipe || {
            echo "安装 MediaPipe..."
            pip install mediapipe
        }
        USE_MMPOSE=false
    fi
fi

if [ $missing -gt 0 ]; then
    echo ""
    echo "安装缺失的基础依赖..."
    pip install flask flask-cors opencv-python numpy pillow
fi

# 设置环境变量以优化 GPU 使用
echo ""
echo "配置 GPU 优化参数..."
export CUDA_VISIBLE_DEVICES=0  # 使用第一块 GPU
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512  # 优化显存分配

# 设置 Flask 参数
export FLASK_ENV=production
export PORT=5000

echo ""
echo "=========================================="
echo "启动 MMPose GPU 服务..."
echo "=========================================="
echo ""
echo "GPU 设备: NVIDIA RTX 3060"
echo "后端模型: ${USE_MMPOSE:+MMPose RTMPose-m (GPU)}"
echo "服务地址: http://localhost:5000"
echo ""
echo "预期性能："
echo "  - FPS: 80-120 (GPU 加速)"
echo "  - 延迟: 8-12 ms"
echo "  - 显存占用: ~2-3 GB"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=========================================="
echo ""

# 启动服务
cd "$(dirname "$0")"
python3 pose_server.py
