#!/bin/bash
# 网络不稳定时的安装方案
# 优先使用清华源和 CPU 版本，确保能跑起来

set -e

echo "========================================"
echo "网络友好的安装方案"
echo "========================================"

# 确保在正确的环境
if [[ "$CONDA_DEFAULT_ENV" != "mmpose_gpu" ]]; then
  echo "❌ 请先激活 mmpose_gpu 环境："
  echo "   conda activate mmpose_gpu"
  exit 1
fi

echo ""
echo "[1/5] 配置清华源..."
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

echo ""
echo "[2/5] 安装基础依赖..."
pip install flask flask-cors opencv-python numpy pillow

echo ""
echo "[3/5] 安装 PyTorch CPU 版本（约 200MB，从 conda 清华源）..."
echo "提示：GPU 版本可以网络好的时候再升级"
# 完全避免 PyTorch 官方源，使用 conda
conda install pytorch torchvision torchaudio cpuonly -c pytorch -y

echo ""
echo "[4/5] 验证 PyTorch..."
if python -c "import torch; print('✓ PyTorch:', torch.__version__)"; then
  echo "✓ PyTorch 安装成功"
else
  echo "❌ PyTorch 安装失败"
  echo "尝试备选方案：只用 MediaPipe（也很好用）"
  pip install mediapipe
fi

echo ""
echo "[5/5] 安装 MMPose..."
pip install -U openmim
pip install mmengine

# mmcv 尝试用 mim
echo "安装 mmcv（如果超时会自动跳过）..."
timeout 60 mim install mmcv || {
  echo "⚠️  mmcv 安装超时，pose_server 会自动使用 MediaPipe 备选方案"
}

pip install mmdet mmpose || echo "⚠️  mmpose 安装失败，pose_server 会使用 MediaPipe"

echo ""
echo "========================================"
echo "✓ 基础环境安装完成！"
echo "========================================"
echo ""
echo "启动服务："
echo "  python pose_server.py"
echo ""
echo "提示："
echo "- 当前使用 CPU 版本 PyTorch"
echo "- pose_server 会自动使用 MediaPipe（也很好用）"
echo "- 网络好的时候可以升级到 GPU 版本："
echo "    pip uninstall torch torchvision torchaudio"
echo "    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
