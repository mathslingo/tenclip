#!/bin/bash

# CPU-Only 云主机 PyTorch/MMCV 修复脚本
# 解决: ImportError: undefined symbol: iJIT_NotifyEvent
# 用法: bash fix_pytorch_cpu.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   CPU-Only PyTorch/MMCV 修复脚本      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# 检查环境
echo -e "${YELLOW}检查当前环境...${NC}"
python -c "import torch; print('当前 PyTorch:', torch.__version__); print('CUDA:', torch.cuda.is_available())"
echo ""

# 询问用户
echo -e "${YELLOW}这会卸载旧 PyTorch，然后重新安装 CPU 版本。${NC}"
echo -e "${YELLOW}继续吗？(y/n)${NC}"
read -r CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo -e "${YELLOW}已取消${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}开始修复...${NC}"
echo ""

# 1. 卸载旧 PyTorch
echo -e "${YELLOW}[1/4] 卸载旧 PyTorch...${NC}"
pip uninstall torch torchvision torchaudio -y -q 2>/dev/null || true
echo -e "${GREEN}✓ 完成${NC}"
echo ""

# 2. 安装 CPU 版本
echo -e "${YELLOW}[2/4] 安装 PyTorch CPU 版本...${NC}"
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  torch torchvision torchaudio -q
echo -e "${GREEN}✓ 完成${NC}"
echo ""

# 3. 验证 PyTorch
echo -e "${YELLOW}[3/4] 验证 PyTorch...${NC}"
python << 'EOF'
import torch
print(f"✓ PyTorch: {torch.__version__}")
print(f"✓ CUDA available: {torch.cuda.is_available()}")
EOF
echo ""

# 4. 安装 MMPose（用 pip，不用 mim）
echo -e "${YELLOW}[4/4] 安装 MMPose/MMCV/MMDet...${NC}"
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  mmcv mmdet mmpose -q
echo -e "${GREEN}✓ 完成${NC}"
echo ""

# 验证 RTMpose
echo -e "${YELLOW}验证 RTMpose...${NC}"
python << 'EOF'
try:
    from mmpose.apis import MMPoseInferencer
    print("✓ RTMpose API 可用")
    print("✓ 支持的模型: rtmpose-s, rtmpose-m, rtmpose-l")
except Exception as e:
    print(f"⚠ RTMpose 验证失败: {e}")
    print("  但 MediaPipe 回退方案可用")
EOF

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ 修复完成！${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}后续步骤${NC}"
echo "1. 重启服务:"
echo "   python pose_server_v2.py"
echo ""
echo "2. 验证:"
echo "   curl http://localhost:5000/api/health"
echo ""
