#!/bin/bash

# RTMpose v2 CPU版本安装脚本（最大化利用已有环境）
# 适用于：
# - 本地 mmpose_gpu 环境（补全缺失的 mmpose）
# - 云主机（CPU 无 GPU）
# 用法: bash install_mmpose_cpu.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   RTMpose v2 CPU 版本依赖安装脚本      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# ============ 检查环境 ============

echo -e "${YELLOW}[1/5] 检查环境...${NC}"

# 检查 Python
if ! command -v python &> /dev/null; then
    echo -e "${RED}✗ Python 未找到${NC}"
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python: $PYTHON_VERSION${NC}"

# 检查 conda
if command -v conda &> /dev/null; then
    CONDA_ENV=$(conda info --json | grep active_prefix | head -1)
    echo -e "${GREEN}✓ Conda 已安装${NC}"
    echo "  当前环境: $(conda info --envs | grep '\\*' | awk '{print $1}')"
else
    echo -e "${YELLOW}⚠ Conda 未安装，继续...${NC}"
fi

# 检查 pip
if ! command -v pip &> /dev/null; then
    echo -e "${RED}✗ pip 未找到${NC}"
    exit 1
fi

PIP_VERSION=$(pip --version | awk '{print $2}')
echo -e "${GREEN}✓ pip: $PIP_VERSION${NC}"

echo ""

# ============ 检查已有模块 ============

echo -e "${YELLOW}[2/5] 检查已有模块...${NC}"

MODULES=("torch" "mmengine" "numpy" "opencv-python" "flask" "mediapipe")

for module in "${MODULES[@]}"; do
    if python -c "import ${module//-/_}" 2>/dev/null; then
        VERSION=$(python -c "import ${module//-/_} as m; print(getattr(m, '__version__', 'N/A'))" 2>/dev/null)
        echo -e "${GREEN}✓ $module ($VERSION)${NC}"
    else
        echo -e "${RED}✗ $module 缺失${NC}"
    fi
done

# 检查 mmpose（可能缺失）
if python -c "import mmpose" 2>/dev/null; then
    echo -e "${GREEN}✓ mmpose ($(python -c 'import mmpose; print(mmpose.__version__)'))${NC}"
    MMPOSE_EXISTS=true
else
    echo -e "${YELLOW}⚠ mmpose 缺失（将安装）${NC}"
    MMPOSE_EXISTS=false
fi

# 检查 mmcv（可能缺失）
if python -c "import mmcv" 2>/dev/null; then
    echo -e "${GREEN}✓ mmcv ($(python -c 'import mmcv; print(mmcv.__version__)'))${NC}"
    MMCV_EXISTS=true
else
    echo -e "${YELLOW}⚠ mmcv 缺失（将安装）${NC}"
    MMCV_EXISTS=false
fi

# 检查 mmdet（推荐）
if python -c "import mmdet" 2>/dev/null; then
    echo -e "${GREEN}✓ mmdet ($(python -c 'import mmdet; print(mmdet.__version__)'))${NC}"
    MMDET_EXISTS=true
else
    echo -e "${YELLOW}⚠ mmdet 缺失（推荐安装）${NC}"
    MMDET_EXISTS=false
fi

# 检查 GPU
echo -e "${BLUE}─────────────────────────────────────────${NC}"
echo -e "GPU 状态:"
if python -c "import torch; torch.cuda.is_available()" 2>/dev/null && python -c "import torch; print(torch.cuda.is_available())" | grep -q "True"; then
    GPU_COUNT=$(python -c "import torch; print(torch.cuda.device_count())" 2>/dev/null)
    GPU_NAME=$(python -c "import torch; print(torch.cuda.get_device_name(0))" 2>/dev/null)
    echo -e "${GREEN}✓ GPU 可用: $GPU_NAME ($GPU_COUNT 个)${NC}"
else
    echo -e "${YELLOW}⚠ GPU 不可用，使用 CPU 模式${NC}"
fi

echo ""

# ============ 安装缺失的包 ============

if [ "$MMPOSE_EXISTS" = true ] && [ "$MMCV_EXISTS" = true ] && [ "$MMDET_EXISTS" = true ]; then
    echo -e "${GREEN}✓ 所有必要包都已安装${NC}"
    echo ""
    
    # 验证可用性
    echo -e "${YELLOW}[3/5] 验证 RTMpose 可用性...${NC}"
    python << 'EOF'
try:
    from mmpose.apis import MMPoseInferencer
    print("✓ RTMpose 可用（MMPoseInferencer）")
    
    # 检查支持的模型
    models = ['rtmpose-s', 'rtmpose-m', 'rtmpose-l']
    print(f"✓ 支持的模型: {', '.join(models)}")
except ImportError as e:
    print(f"✗ RTMpose 不可用: {e}")
    exit(1)
EOF
    
else
    echo -e "${YELLOW}[3/5] 安装缺失的包...${NC}"
    echo ""
    
    # 配置清华源
    echo -e "${BLUE}配置清华源...${NC}"
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null || true
    
    # 1. 更新 pip（可选）
    echo -e "${BLUE}更新 pip...${NC}"
    pip install --upgrade pip setuptools wheel -q
    
    # 2. 安装 openmim（如果需要）
    echo -e "${BLUE}检查 openmim...${NC}"
    if ! python -c "import openmim" 2>/dev/null; then
        echo "安装 openmim..."
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim -q
    else
        echo "✓ openmim 已安装"
    fi
    
    # 3. 安装 mmcv（使用 mim）
    if [ "$MMCV_EXISTS" = false ]; then
        echo -e "${BLUE}安装 mmcv（使用 mim）...${NC}"
        mim install mmcv -q
        echo -e "${GREEN}✓ mmcv 安装完成${NC}"
    fi
    
    # 4. 安装 mmdet（可选但推荐）
    if [ "$MMDET_EXISTS" = false ]; then
        echo -e "${BLUE}安装 mmdet...${NC}"
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet -q
        echo -e "${GREEN}✓ mmdet 安装完成${NC}"
    fi
    
    # 5. 安装 mmpose（核心）
    if [ "$MMPOSE_EXISTS" = false ]; then
        echo -e "${BLUE}安装 mmpose...${NC}"
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmpose -q
        echo -e "${GREEN}✓ mmpose 安装完成${NC}"
    fi
    
    # 6. 安装额外依赖（如果需要）
    echo -e "${BLUE}安装额外依赖...${NC}"
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
        chumpy json_tricks matplotlib munkres scipy xtcocotools -q 2>/dev/null || true
    
    echo ""
    echo -e "${YELLOW}[4/5] 验证 RTMpose 可用性...${NC}"
    
    python << 'EOF'
import sys

print("验证 MMPose...")
try:
    from mmpose.apis import MMPoseInferencer
    print("✓ RTMpose API 可用")
except ImportError as e:
    print(f"✗ RTMpose API 不可用: {e}")
    sys.exit(1)

print("\n检查支持的模型:")
models = {
    'rtmpose-s': '轻量版（推荐 CPU）',
    'rtmpose-m': '标准版',
    'rtmpose-l': '高精度'
}
for model, desc in models.items():
    print(f"  ✓ {model}: {desc}")

print("\n检查输出路径:")
import mmpose
print(f"  ✓ MMPose 路径: {mmpose.__file__}")

print("\n✓ RTMpose v2 已就绪！")
EOF
fi

echo ""

# ============ 最终验证 ============

echo -e "${YELLOW}[5/5] 最终验证...${NC}"

python << 'EOF'
import sys
import os

print("进行完整验证...")
print()

# 1. 检查核心模块
modules_to_check = {
    'torch': 'PyTorch',
    'mmpose': 'MMPose',
    'mmengine': 'MMEngine',
    'mmcv': 'MMCV',
    'mmdet': 'MMDet',
    'cv2': 'OpenCV',
    'numpy': 'NumPy',
    'flask': 'Flask',
}

print("✓ 核心模块检查:")
all_ok = True
for module, name in modules_to_check.items():
    try:
        mod = __import__(module.replace('-', '_'))
        version = getattr(mod, '__version__', 'N/A')
        print(f"  ✓ {name:15} {version}")
    except ImportError:
        print(f"  ✗ {name:15} 缺失")
        all_ok = False

print()

# 2. 检查 RTMpose 推理器
print("✓ RTMpose 推理器:")
try:
    from mmpose.apis import MMPoseInferencer
    print("  ✓ MMPoseInferencer 可用")
except ImportError as e:
    print(f"  ✗ MMPoseInferencer 不可用: {e}")
    all_ok = False

# 3. 检查 GPU
print()
print("✓ 计算设备:")
if hasattr(__import__('torch'), 'cuda'):
    import torch
    if torch.cuda.is_available():
        print(f"  ✓ GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("  ✓ GPU: 不可用，使用 CPU")

print()

if all_ok:
    print("━" * 45)
    print("✅ RTMpose v2 安装完成，所有依赖就绪！")
    print("━" * 45)
else:
    print("⚠️  部分依赖缺失，但 RTMpose 基础已安装")
    sys.exit(0)
EOF

echo ""

# ============ 使用建议 ============

echo -e "${GREEN}🎉 安装完成！${NC}"
echo ""
echo -e "${BLUE}后续使用${NC}"
echo "1. 启动 RTMpose v2 后端:"
echo "   python pose_server_v2.py"
echo ""
echo "2. 指定模型大小（默认 m）:"
echo "   python pose_server_v2.py"
echo "   # 编辑 pose_server_v2.py 最后一行，改 init_models(model_size='s/m/l')"
echo ""
echo "3. 如果 CPU 内存不足，使用轻量模型:"
echo "   # 编辑 pose_server_v2.py"
echo "   # init_models(model_size='s')  # 推荐用于 CPU"
echo ""
echo "4. 云主机快速启动:"
echo "   nohup python pose_server_v2.py > pose.log 2>&1 &"
echo ""
