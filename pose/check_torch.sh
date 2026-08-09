#!/bin/bash

echo "========================================"
echo "检查 tenclip 环境的 PyTorch"
echo "========================================"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate tenclip
echo "1. PyTorch 是否能正常导入？"
python -c "import torch; print('✓ PyTorch:', torch.__version__); print('✓ CUDA:', torch.cuda.is_available())" && echo "✓ tenclip 的 torch 正常" || echo "✗ tenclip 的 torch 有问题"

echo ""
echo "2. tenclip 环境中的 MKL 相关包："
conda list | grep -E "(mkl|intel)" | head -10

echo ""
echo "3. torch 包大小（判断是否完整）："
du -sh ~/miniconda3/envs/tenclip/lib/python3.*/site-packages/torch 2>/dev/null || echo "未找到"

echo ""
echo "========================================"
echo "检查 mmpose_gpu 环境"
echo "========================================"
conda activate mmpose_gpu
echo "4. mmpose_gpu 环境中的 MKL 相关包："
conda list | grep -E "(mkl|intel)" || echo "无 MKL 包"

echo ""
echo "5. mmpose_gpu 中是否已有 torch："
conda list | grep torch || echo "无 torch"

echo ""
echo "========================================"
echo "建议"
echo "========================================"
