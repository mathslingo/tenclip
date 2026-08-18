#!/bin/bash

# RTMpose v2 快速启动脚本
# 用法: bash start_rtmpose_v2.sh [s|m|l]
# 示例:
#   bash start_rtmpose_v2.sh        # 默认使用 m (标准)
#   bash start_rtmpose_v2.sh s      # 使用 s (轻量)
#   bash start_rtmpose_v2.sh l      # 使用 l (高精度)

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认模型大小
MODEL_SIZE="${1:-m}"

# 验证模型大小
if [[ ! "$MODEL_SIZE" =~ ^[sml]$ ]]; then
    echo -e "${RED}✗ 模型大小只能是 s、m 或 l${NC}"
    echo "用法: bash $0 [s|m|l]"
    exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    RTMpose v2 实时姿态检测服务        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# 检查环境
echo -e "${YELLOW}[1/4] 检查环境...${NC}"

if ! command -v conda &> /dev/null; then
    echo -e "${RED}✗ conda 未找到，请先安装 Miniconda/Anaconda${NC}"
    exit 1
fi

if ! command -v python &> /dev/null; then
    echo -e "${RED}✗ python 未找到，请先激活 conda 环境${NC}"
    exit 1
fi

echo -e "${GREEN}✓ conda 和 python 已就绪${NC}"
echo ""

# 检查依赖
echo -e "${YELLOW}[2/4] 检查依赖...${NC}"

python << EOF
import sys
required_modules = ['flask', 'torch', 'mmpose']
missing = []

for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        missing.append(module)

if missing:
    print(f"✗ 缺少依赖: {', '.join(missing)}")
    print("请运行以下命令安装:")
    print("")
    print("  # 基础依赖")
    print("  pip install flask flask-cors opencv-python numpy pillow")
    print("")
    print("  # PyTorch")
    print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
    print("")
    print("  # MMPose")
    print("  pip install -U openmim")
    print("  mim install mmengine mmcv mmdet mmpose")
    sys.exit(1)
else:
    print("✓ 所有依赖已就绪")

# 检查 GPU
import torch
if torch.cuda.is_available():
    print(f"✓ GPU 可用: {torch.cuda.get_device_name(0)}")
else:
    print("⚠ GPU 不可用，将使用 CPU（性能较慢）")
EOF

echo ""

# 显示模型信息
echo -e "${YELLOW}[3/4] 模型配置...${NC}"

case $MODEL_SIZE in
    s)
        echo -e "${GREEN}模型: rtmpose-s (轻量)${NC}"
        echo "  推理时间: 8-15 ms"
        echo "  FPS: 60-100"
        echo "  显存: 1.5 GB"
        ;;
    m)
        echo -e "${GREEN}模型: rtmpose-m (标准，推荐)${NC}"
        echo "  推理时间: 15-25 ms"
        echo "  FPS: 40-65"
        echo "  显存: 3-4 GB"
        ;;
    l)
        echo -e "${GREEN}模型: rtmpose-l (高精度)${NC}"
        echo "  推理时间: 30-50 ms"
        echo "  FPS: 20-33"
        echo "  显存: 8-10 GB"
        ;;
esac

echo ""

# 启动服务
echo -e "${YELLOW}[4/4] 启动服务...${NC}"
echo -e "${GREEN}✓ 启动 RTMpose v2 后端${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Web UI: http://localhost:5000"
echo "API:    http://localhost:5000/api/detect"
echo "Health: http://localhost:5000/api/health"
echo ""
echo "按 Ctrl+C 停止服务"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 创建临时启动脚本
cat > /tmp/start_rtmpose_v2_temp.py << PYTHON_EOF
import sys
sys.path.insert(0, '$(pwd)')

# 注入模型大小
import os
os.environ['RTMPOSE_MODEL_SIZE'] = '$MODEL_SIZE'

# 启动服务
from pose_server_v2 import app, init_models

try:
    init_models(model_size='$MODEL_SIZE')
except Exception as e:
    print(f"模型初始化失败: {e}")
    sys.exit(1)

app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
PYTHON_EOF

python /tmp/start_rtmpose_v2_temp.py

# 清理
rm -f /tmp/start_rtmpose_v2_temp.py
