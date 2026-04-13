#!/bin/bash

# TenClip - VLM模型权重下载脚本 (Linux版)
# 该脚本用于在conda环境中下载Qwen2-VL-2B-Instruct模型权重
# 默认从ModelScope下载（国内访问更快），可通过环境变量切换为Hugging Face

set -e  # 遇到错误立即退出

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== TenClip VLM模型权重下载 ==="
echo "脚本位置: $SCRIPT_DIR"
echo

# 检查conda是否已安装
if ! command -v conda &> /dev/null; then
    echo "错误: 未找到conda命令"
    echo "请确保已安装Anaconda或Miniconda，并将其添加到PATH中"
    exit 1
fi

# 检查tenclip环境是否存在
if ! conda env list | grep -q "^tenclip "; then
    echo "错误: 未找到名为'tenclip'的conda环境"
    echo "请先运行: bash setup-conda-env.sh 或 bash setup-conda-env.bat"
    exit 1
fi

echo "检测到conda环境，开始下载VLM模型权重..."
echo "默认从ModelScope下载（国内访问更稳定）"
echo "如需使用HuggingFace，请设置环境变量: export TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface"
echo

# 运行下载脚本
conda run -n tenclip python scripts/download_vlm_weights.py

# 检查命令执行状态
if [ $? -eq 0 ]; then
    echo
    echo "✅ VLM模型权重下载完成！"
    echo
    echo "下一步启动应用:"
    echo "  bash start-conda-llm.sh"
    echo "或直接运行:"
    echo "  conda run -n tenclip python app.py"
else
    echo
    echo "❌ 下载过程中出现错误"
    echo "请检查网络连接和conda环境配置"
    echo "也可以尝试手动运行: conda run -n tenclip python scripts/download_vlm_weights.py"
    exit 1
fi
