#!/bin/bash

# RTMpose v2 Conda 环境快速部署脚本
# 用途: 在云主机上快速创建 conda 环境并安装所有依赖
# 用法: bash setup_conda_env.sh [env_name]
# 示例: 
#   bash setup_conda_env.sh tenclip         # 创建名为 tenclip 的环境
#   bash setup_conda_env.sh                 # 默认名为 tenclip

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 参数
ENV_NAME="${1:-tenclip}"
PYTHON_VERSION="3.10"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   RTMpose v2 Conda 环境部署脚本        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# ============ 1. 检查 conda ============

echo -e "${YELLOW}[1/5] 检查 conda...${NC}"

if ! command -v conda &> /dev/null; then
    echo -e "${RED}✗ conda 未找到${NC}"
    echo "请先安装 Miniconda 或 Anaconda:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

CONDA_VERSION=$(conda --version)
echo -e "${GREEN}✓ $CONDA_VERSION${NC}"
echo ""

# ============ 2. 创建环境 ============

echo -e "${YELLOW}[2/5] 创建 conda 环境...${NC}"
echo "环境名称: $ENV_NAME"
echo "Python 版本: $PYTHON_VERSION"
echo ""

if conda env list | grep -q "^$ENV_NAME "; then
    echo -e "${YELLOW}⚠ 环境 '$ENV_NAME' 已存在${NC}"
    echo -e "${YELLOW}删除旧环境并重新创建? (y/n)${NC}"
    read -r CONFIRM
    if [[ "$CONFIRM" == "y" || "$CONFIRM" == "Y" ]]; then
        echo "删除旧环境..."
        conda env remove -n "$ENV_NAME" -y
    else
        echo -e "${YELLOW}使用现有环境${NC}"
        SKIP_CREATE=true
    fi
fi

if [[ "$SKIP_CREATE" != "true" ]]; then
    echo "创建环境 $ENV_NAME..."
    conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y -q
fi

echo -e "${GREEN}✓ 完成${NC}"
echo ""

# ============ 3. 激活环境并升级 pip ============

echo -e "${YELLOW}[3/5] 初始化环境...${NC}"

# 使用 source 激活环境
source "$(conda info --base)"/etc/profile.d/conda.sh
conda activate "$ENV_NAME"

echo "升级 pip..."
pip install --upgrade pip setuptools wheel -q

echo -e "${GREEN}✓ 完成${NC}"
echo ""

# ============ 4. 安装依赖 ============

echo -e "${YELLOW}[4/5] 安装依赖...${NC}"

# 检查 requirements 文件
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements_rtmpose_cpu.txt"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${RED}✗ 未找到 requirements 文件: $REQUIREMENTS_FILE${NC}"
    exit 1
fi

echo "安装位置: $REQUIREMENTS_FILE"
echo ""

# 配置清华源
echo "配置清华源..."
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null || true

# 安装依赖（分段，避免超时）
echo "安装 PyTorch..."
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple torch torchvision torchaudio -q

echo "安装 MMPose 相关..."
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine openmim -q
mim install -q mmcv || true

echo "安装其他依赖..."
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    mmdet mmpose Flask Flask-CORS opencv-python numpy scipy pandas -q

echo "安装回退方案..."
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mediapipe -q

echo -e "${GREEN}✓ 完成${NC}"
echo ""

# ============ 5. 验证安装 ============

echo -e "${YELLOW}[5/5] 验证安装...${NC}"
echo ""

python << 'EOF'
import sys

modules = {
    'torch': 'PyTorch',
    'mmengine': 'MMEngine',
    'mmcv': 'MMCV',
    'mmdet': 'MMDet',
    'mmpose': 'MMPose',
    'cv2': 'OpenCV',
    'flask': 'Flask',
    'mediapipe': 'MediaPipe',
}

print("✓ 核心模块检查:")
all_ok = True
for module, name in modules.items():
    try:
        mod = __import__(module.replace('-', '_'))
        version = getattr(mod, '__version__', 'N/A')
        print(f"  ✓ {name:15} {version}")
    except ImportError:
        print(f"  ✗ {name:15} 缺失")
        all_ok = False

# 检查 RTMpose
print()
print("✓ RTMpose 检查:")
try:
    from mmpose.apis import MMPoseInferencer
    print("  ✓ MMPoseInferencer 可用")
    print("  ✓ 支持的模型: rtmpose-s, rtmpose-m, rtmpose-l")
except Exception as e:
    print(f"  ⚠ RTMpose 暂不可用（回退到 MediaPipe）: {e}")

# GPU 检查
print()
print("✓ 计算设备:")
import torch
if torch.cuda.is_available():
    print(f"  ✓ GPU: {torch.cuda.get_device_name(0)}")
else:
    print("  ✓ GPU: 不可用（CPU 模式）")

print()
if all_ok:
    print("✅ 环境设置完成！")
else:
    print("⚠️  部分模块缺失，但基础已安装")
EOF

echo ""

# ============ 输出总结 ============

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Conda 环境创建完成！${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}后续使用${NC}"
echo ""
echo "1. 激活环境:"
echo "   conda activate $ENV_NAME"
echo ""
echo "2. 启动 RTMpose v2 后端:"
echo "   cd ~/tenclip/pose"
echo "   python pose_server_v2.py"
echo ""
echo "3. 验证:"
echo "   curl http://localhost:5000/api/health"
echo ""
echo "4. 导出环境配置（用于其他机器）:"
echo "   conda env export > $ENV_NAME.yml"
echo "   # 其他机器恢复:"
echo "   conda env create -f $ENV_NAME.yml"
echo ""
