#!/bin/bash
# 从 tenclip 复制 PyTorch 到 mmpose_gpu（适合网络不好的情况）

set -e

echo "========================================"
echo "方案 A：复制 PyTorch + 补装依赖（快速）"
echo "========================================"

# 1. 找到 tenclip 和 mmpose_gpu 的 site-packages 路径
TENCLIP_SITE=$(conda run -n tenclip python -c "import site; print(site.getsitepackages()[0])")
MMPOSE_SITE=$(conda run -n mmpose_gpu python -c "import site; print(site.getsitepackages()[0])")

echo "源环境: $TENCLIP_SITE"
echo "目标环境: $MMPOSE_SITE"

# 2. 复制 torch 相关包（约 2-3GB）
echo ""
echo "[1/3] 复制 PyTorch 包（可能需要 1-2 分钟）..."
for pkg in torch torchvision torchaudio; do
  if [ -d "$TENCLIP_SITE/$pkg" ]; then
    echo "  复制 $pkg..."
    rm -rf "$MMPOSE_SITE/$pkg"
    cp -r "$TENCLIP_SITE/$pkg" "$MMPOSE_SITE/"
    
    # 同时复制 .dist-info 目录
    for dist_info in "$TENCLIP_SITE"/${pkg}*.dist-info; do
      if [ -d "$dist_info" ]; then
        cp -r "$dist_info" "$MMPOSE_SITE/"
      fi
    done
  fi
done

# 3. 安装 MKL 依赖（解决 iJIT_NotifyEvent 错误）
echo ""
echo "[2/3] 安装 Intel MKL 依赖（小文件，网络需求低）..."
conda activate mmpose_gpu
conda install mkl mkl-service intel-openmp -y

# 4. 测试 PyTorch
echo ""
echo "[3/3] 测试 PyTorch..."
python << 'EOF'
import torch
print(f"✓ PyTorch: {torch.__version__}")
print(f"✓ CUDA:    {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"✓ GPU:     {torch.cuda.get_device_name(0)}")
print("\n🎉 PyTorch 复制成功！")
EOF

echo ""
echo "========================================"
echo "接下来安装 MMPose..."
echo "========================================"
echo "pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim"
echo "pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine"
echo "mim install mmcv"
echo "pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose"
