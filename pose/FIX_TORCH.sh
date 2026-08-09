#!/bin/bash
# 修复 mmpose_gpu 环境的 torch 问题
# 针对 "undefined symbol: iJIT_NotifyEvent" 错误

set -e

echo "========================================"
echo "修复 torch 的 MKL 依赖问题"
echo "========================================"

# 确保在正确的环境
if [[ "$CONDA_DEFAULT_ENV" != "mmpose_gpu" ]]; then
  echo "❌ 请先激活 mmpose_gpu 环境："
  echo "   conda activate mmpose_gpu"
  exit 1
fi

echo ""
echo "[1/3] 卸载有问题的 torch..."
pip uninstall -y torch torchvision torchaudio 2>/dev/null || echo "未安装或已卸载"

echo ""
echo "[2/3] 重新安装 torch（从官方源，约 800MB）..."
echo "这可能需要 5-15 分钟，取决于网速..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo ""
echo "[3/3] 验证安装..."
if python -c "import torch; print('✓ PyTorch:', torch.__version__, '\n✓ CUDA:', torch.cuda.is_available())"; then
  echo ""
  echo "========================================"
  echo "✓ torch 修复成功！"
  echo "========================================"
  echo ""
  echo "继续安装 mmpose："
  echo "  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim"
  echo "  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine"
  echo "  mim install mmcv"
  echo "  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose"
else
  echo ""
  echo "========================================"
  echo "❌ torch 安装失败"
  echo "========================================"
  echo "可能的原因："
  echo "1. 网络问题 - 请检查网络连接"
  echo "2. 磁盘空间不足 - 需要约 2GB 空间"
  echo "3. Python 版本不兼容 - 当前是 $(python --version)"
  exit 1
fi
