#!/bin/bash
# MMPose 环境配置脚本
# 基于 mmpose 官方 requirements
# 针对 NVIDIA RTX 3060 + CUDA 13.0 优化

set -e

echo "=========================================="
echo "MMPose 环境配置"
echo "Python 3.10 + PyTorch + CUDA 12.1"
echo "=========================================="
echo ""

# 1. 创建新环境
ENV_NAME="mmpose_gpu"
PYTHON_VERSION="3.10"

echo "创建 conda 环境: $ENV_NAME (Python $PYTHON_VERSION)"
conda create -n $ENV_NAME python=$PYTHON_VERSION -y

echo ""
echo "激活环境..."
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

# 2. 配置 pip 镜像源
echo ""
echo "配置 pip 清华镜像源..."
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 安装 PyTorch (CUDA 12.1，兼容 CUDA 13.0)
echo ""
echo "安装 PyTorch + CUDA 12.1..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 验证 PyTorch
echo ""
echo "验证 PyTorch 安装..."
python << 'EOF'
import torch
print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA 版本: {torch.version.cuda}")
    print(f"GPU 设备: {torch.cuda.get_device_name(0)}")
    print(f"GPU 数量: {torch.cuda.device_count()}")
else:
    print("警告: CUDA 不可用，请检查驱动")
EOF

# 4. 安装 mmpose build 依赖
echo ""
echo "安装构建依赖..."
pip install numpy

# 5. 安装 mmcv (OpenMMLab 核心库)
echo ""
echo "安装 MMCV..."
pip install -U openmim
mim install mmengine
mim install "mmcv>=2.0.1"

# 6. 安装 mmpose runtime 依赖
echo ""
echo "安装 MMPose 运行时依赖..."
pip install chumpy
pip install json_tricks
pip install matplotlib
pip install munkres
pip install opencv-python
pip install pillow
pip install scipy
pip install xtcocotools

# 7. 安装 mmdet (目标检测，mmpose 需要)
echo ""
echo "安装 MMDetection..."
mim install "mmdet>=3.0.0"

# 8. 安装 mmpose
echo ""
echo "安装 MMPose..."
mim install "mmpose>=1.0.0"

# 9. 安装 Flask 后端依赖
echo ""
echo "安装 Flask 后端依赖..."
pip install flask flask-cors

# 10. 验证完整安装
echo ""
echo "=========================================="
echo "验证安装"
echo "=========================================="
python << 'EOF'
import sys

packages = {
    'torch': 'PyTorch',
    'torchvision': 'TorchVision',
    'mmengine': 'MMEngine',
    'mmcv': 'MMCV',
    'mmdet': 'MMDetection',
    'mmpose': 'MMPose',
    'cv2': 'OpenCV',
    'flask': 'Flask',
    'numpy': 'NumPy',
    'PIL': 'Pillow',
}

print("\n安装验证:\n")
all_ok = True
for module, name in packages.items():
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'N/A')
        print(f"  ✓ {name:20} {version}")
    except ImportError:
        print(f"  ✗ {name:20} 未安装")
        all_ok = False

# GPU 检查
print("\nGPU 状态:\n")
import torch
if torch.cuda.is_available():
    print(f"  ✓ GPU: {torch.cuda.get_device_name(0)}")
    print(f"  ✓ 显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    print(f"  ✓ CUDA: {torch.version.cuda}")
else:
    print("  ✗ GPU 不可用")
    all_ok = False

print("\n" + "="*50)
if all_ok:
    print("✓ 所有依赖安装成功！")
    print("\n下一步:")
    print("  cd ~/code/tenclip/pose")
    print("  conda activate mmpose_gpu")
    print("  python pose_server.py")
else:
    print("✗ 部分依赖安装失败，请检查错误信息")
    sys.exit(1)
print("="*50)
EOF

echo ""
echo "=========================================="
echo "环境配置完成！"
echo "=========================================="
echo ""
echo "使用方法:"
echo "  conda activate $ENV_NAME"
echo "  cd ~/code/tenclip/pose"
echo "  python pose_server.py"
echo ""
