#!/bin/bash
# MMPose GPU 环境完整安装命令
# 使用前确保已激活 mmpose_gpu 环境：conda activate mmpose_gpu

set -e  # 遇到错误立即停止

echo "========================================"
echo "开始安装 MMPose GPU 环境依赖"
echo "========================================"

# 1. 基础依赖（Flask、OpenCV 等）
echo ""
echo "[1/5] 安装基础依赖（Flask、OpenCV）..."
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  flask flask-cors opencv-python numpy pillow

# 2. PyTorch（用 pip 安装，自带完整依赖，比 conda 快）
echo ""
echo "[2/5] 清理并安装 PyTorch + CUDA 12.1（需要几分钟，约 800MB）..."
# 先卸载可能存在的旧版本
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
conda uninstall -y pytorch torchvision torchaudio 2>/dev/null || true

# 用 pip 从官方源安装（自包含 MKL，避免依赖冲突）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
  
# 验证 PyTorch 能否正常导入
if python -c "import torch; print(f'✓ PyTorch {torch.__version__} 安装成功, CUDA: {torch.cuda.is_available()}')"; then
  echo "✓ PyTorch 安装成功"
else
  echo "❌ PyTorch 安装失败，请检查网络或尝试手动安装"
  exit 1
fi

# 3. 安装 openmim 和 mmengine
echo ""
echo "[3/5] 安装 OpenMMLab 基础工具..."
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine

# 4. ⚠️ mmcv 必须用 mim（不要用 pip，会尝试从源码编译）
echo ""
echo "[4/5] 安装 mmcv（预编译版本，避免 pkg_resources 错误）..."
mim install mmcv

# 5. 安装 mmdet、mmpose 和其他依赖
echo ""
echo "[5/5] 安装 MMPose 及其他依赖..."
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  chumpy json_tricks matplotlib munkres scipy xtcocotools

# 验证安装
echo ""
echo "========================================"
echo "验证安装结果..."
echo "========================================"
python << 'EOF'
import flask
import torch
import mmengine
import mmcv
import mmdet
import mmpose

print(f"✓ Flask:    {flask.__version__}")
print(f"✓ PyTorch:  {torch.__version__}")
print(f"✓ CUDA:     {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"✓ GPU:      {torch.cuda.get_device_name(0)}")
print(f"✓ MMEngine: {mmengine.__version__}")
print(f"✓ MMCV:     {mmcv.__version__}")
print(f"✓ MMDet:    {mmdet.__version__}")
print(f"✓ MMPose:   {mmpose.__version__}")
print("\n🎉 全部安装成功！")
EOF

echo ""
echo "========================================"
echo "可以启动服务了："
echo "  python pose_server.py"
echo "========================================"
