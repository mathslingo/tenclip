#!/bin/bash
# 修复 MediaPipe 安装和导入问题

set -e

echo "========================================"
echo "修复 MediaPipe"
echo "========================================"

if [[ "$CONDA_DEFAULT_ENV" != "mmpose_gpu" ]]; then
  echo "❌ 请先激活 mmpose_gpu 环境："
  echo "   conda activate mmpose_gpu"
  exit 1
fi

echo ""
echo "[1/3] 卸载有问题的 MediaPipe..."
pip uninstall -y mediapipe || echo "未安装"

echo ""
echo "[2/3] 安装稳定版 MediaPipe 0.10.14..."
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mediapipe==0.10.14

echo ""
echo "[3/3] 验证..."
python << 'EOF'
import mediapipe as mp
print(f"✓ MediaPipe: {mp.__version__}")
print(f"✓ solutions 可用: {hasattr(mp, 'solutions')}")
if hasattr(mp, 'solutions'):
    print(f"✓ pose 可用: {hasattr(mp.solutions, 'pose')}")
    print("\n✓ MediaPipe 修复成功！")
else:
    print("\n⚠️  版本可能不对，但可以尝试启动服务")
EOF

echo ""
echo "========================================"
echo "现在可以启动服务了："
echo "  python pose_server.py"
echo "======================================"
