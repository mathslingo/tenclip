#!/bin/bash
# 检查两个环境的 Python 版本

echo "tenclip 环境："
source ~/miniconda3/etc/profile.d/conda.sh
conda activate tenclip
python --version
echo "torch 位置: $(python -c 'import torch, os; print(os.path.dirname(torch.__file__))' 2>/dev/null || echo '未安装或有问题')"

echo ""
echo "mmpose_gpu 环境："
conda activate mmpose_gpu  
python --version
echo "torch 位置: $(python -c 'import torch, os; print(os.path.dirname(torch.__file__))' 2>/dev/null || echo '未安装或导入失败')"

echo ""
echo "结论："
tenclip_py=$(conda activate tenclip && python --version | grep -oP '\d+\.\d+')
mmpose_py=$(conda activate mmpose_gpu && python --version | grep -oP '\d+\.\d+')
echo "tenclip Python: $tenclip_py"
echo "mmpose_gpu Python: $mmpose_py"
