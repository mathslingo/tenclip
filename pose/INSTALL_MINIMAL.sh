#!/bin/bash
# 最小化下载方案：优先修复现有 torch，失败后再下载

set +e  # 允许错误继续执行

echo "========================================"
echo "方案：修复 mmpose_gpu 环境的 torch"
echo "（网络不好时最优方案）"
echo "========================================"

source ~/miniconda3/etc/profile.d/conda.sh
conda activate mmpose_gpu

echo ""
echo "当前环境："
python --version
echo ""

# ============================================
# 方案 1：只安装 MKL 依赖（最小下载，约 50MB）
# ============================================
echo "[方案 1] 尝试只安装 MKL 修复现有 torch..."
echo "（下载约 50MB）"
echo ""

# 检查是否已有 torch
if python -c "import torch; print('torch 已存在:', torch.__version__)" 2>/dev/null; then
    echo "✓ torch 已安装，尝试安装 MKL 修复导入问题..."
    conda install mkl mkl-service intel-openmp -c conda-forge -y
    
    echo ""
    echo "测试修复结果..."
    if python -c "import torch; print('✓ 修复成功! PyTorch:', torch.__version__, 'CUDA:', torch.cuda.is_available())"; then
        echo ""
        echo "🎉 方案 1 成功！继续安装 MMPose..."
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine
        mim install mmcv
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
          chumpy json_tricks matplotlib munkres scipy xtcocotools
        
        echo ""
        python -c "import flask, torch, mmpose; print('✓ 全部完成')"
        exit 0
    else
        echo "✗ 方案 1 失败，torch 仍无法导入"
    fi
else
    echo "✗ torch 未安装或已损坏"
fi

# ============================================
# 方案 2：pip 安装 torch（中等下载，约 800MB）
# ============================================
echo ""
echo "[方案 2] 使用 pip 从官方源安装 torch..."
echo "（下载约 800MB，比 conda 省 1GB+）"
echo ""
read -p "是否继续？网络不好可能需要 10-20 分钟 [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 清理旧版本
    pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
    conda uninstall -y pytorch torchvision torchaudio 2>/dev/null || true
    
    # 安装 torch 2.11.0 (匹配 tenclip 的版本，Python 3.10 兼容)
    pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 \
      --index-url https://download.pytorch.org/whl/cu121
    
    echo ""
    echo "测试安装结果..."
    if python -c "import torch; print('✓ PyTorch:', torch.__version__, 'CUDA:', torch.cuda.is_available())"; then
        echo ""
        echo "🎉 方案 2 成功！继续安装 MMPose..."
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine
        mim install mmcv
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
          chumpy json_tricks matplotlib munkres scipy xtcocotools
        
        echo ""
        python -c "import flask, torch, mmpose; print('✓ 全部完成')"
        exit 0
    else
        echo "✗ 方案 2 也失败了"
    fi
fi

# ============================================
# 方案 3：conda 安装（最稳但下载最大，约 2GB）
# ============================================
echo ""
echo "[方案 3] 使用 conda 安装（最稳定但下载最大）..."
echo "（下载约 2GB，可能需要 20-40 分钟）"
echo ""
read -p "是否继续？[y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
    conda uninstall -y pytorch torchvision torchaudio 2>/dev/null || true
    
    conda install pytorch torchvision torchaudio pytorch-cuda=12.1 \
      -c pytorch -c nvidia -y
    
    echo ""
    if python -c "import torch; print('✓ PyTorch:', torch.__version__, 'CUDA:', torch.cuda.is_available())"; then
        echo ""
        echo "🎉 方案 3 成功！继续安装 MMPose..."
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine
        mim install mmcv
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
          chumpy json_tricks matplotlib munkres scipy xtcocotools
        
        echo ""
        python -c "import flask, torch, mmpose; print('✓ 全部完成')"
        exit 0
    fi
fi

echo ""
echo "========================================"
echo "所有方案均未成功"
echo "建议：网络好时重试方案 2 或 3"
echo "========================================"
