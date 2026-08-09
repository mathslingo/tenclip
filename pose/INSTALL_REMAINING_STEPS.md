# MMPose GPU 环境配置 - 剩余安装步骤

## 当前状态
- ✅ conda 环境 `mmpose_gpu` 已创建（Python 3.10）
- ❌ PyTorch 未安装
- ❌ MMPose 及依赖未安装

## 安装步骤

### 方式 1：使用 Conda 安装 PyTorch（推荐）⭐

最简单可靠，自动匹配 CUDA 版本：

```bash
# 激活环境
conda activate mmpose_gpu

# 安装 PyTorch (CUDA 12.1，兼容你的 CUDA 13.0)
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y

# 验证安装
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

### 方式 2：使用 pip 安装 PyTorch

需要从官方源安装（不能用清华源）：

```bash
conda activate mmpose_gpu

# 临时取消镜像源
pip config unset global.index-url

# 从 PyTorch 官方安装
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 验证
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}')"

# 重新设置清华源（用于后续安装）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 方式 3：从 tenclip 环境复制 PyTorch（快速方案）

如果你的 `tenclip` 环境中已经有 PyTorch 2.11.0+cu130，可以直接复用：

```bash
# 1. 检查 tenclip 中的 torch 版本
conda activate tenclip
python -c "import torch; print(torch.__version__)"
# 输出应该是: 2.11.0+cu130

# 2. 导出 tenclip 环境中 PyTorch 相关包的列表
pip list | grep -E "torch|nvidia" > /tmp/torch_packages.txt
cat /tmp/torch_packages.txt

# 3. 切换到 mmpose_gpu 环境
conda activate mmpose_gpu

# 4. 从 conda 缓存安装（如果有）
conda install pytorch torchvision torchaudio pytorch-cuda=13.0 -c pytorch -c nvidia -y

# 或者使用相同的 pip 源
pip install torch==2.11.0 torchvision==0.26.0 torchaudio --index-url https://download.pytorch.org/whl/cu130

# 5. 验证
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}')"
```

---

## 安装 MMPose 及依赖

PyTorch 安装成功后，继续安装其他包：

```bash
conda activate mmpose_gpu

# 1. 设置清华源（加速下载）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 安装 OpenMMLab 工具
pip install -U openmim

# 3. 安装 MMPose 核心依赖
pip install mmengine
pip install mmcv
pip install mmdet
pip install mmpose

# 4. 安装 MMPose 运行时依赖（基于官方 requirements）
pip install chumpy json_tricks matplotlib munkres opencv-python pillow scipy xtcocotools

# 5. 安装 Flask 后端
pip install flask flask-cors

# 6. 完整验证
python << 'EOF'
import torch
import mmengine
import mmcv
import mmdet
import mmpose

print("\n" + "="*50)
print("环境验证")
print("="*50)
print(f"✓ PyTorch: {torch.__version__}")
print(f"✓ CUDA: {torch.version.cuda}")
print(f"✓ GPU Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"✓ GPU: {torch.cuda.get_device_name(0)}")
    print(f"✓ 显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
print(f"✓ MMEngine: {mmengine.__version__}")
print(f"✓ MMCV: {mmcv.__version__}")
print(f"✓ MMDet: {mmdet.__version__}")
print(f"✓ MMPose: {mmpose.__version__}")
print("="*50)
print("✓ 所有依赖安装成功！")
print("\n下一步:")
print("  cd ~/code/tenclip/pose")
print("  python pose_server.py")
print("="*50)
EOF
```

---

## 测试 MMPose 模型

```bash
conda activate mmpose_gpu
cd ~/code/tenclip/pose

# 快速测试 RTMPose 模型
python << 'EOF'
import torch
import numpy as np
from mmpose.apis import MMPoseInferencer

print("正在初始化 RTMPose 模型...")
model = MMPoseInferencer(
    pose2d='rtmpose-s',  # 轻量模型
    device='cuda:0' if torch.cuda.is_available() else 'cpu'
)
print(f"✓ 模型加载成功 (设备: {'GPU' if torch.cuda.is_available() else 'CPU'})")

# 测试推理
dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
result = model(dummy_img, return_vis=False)
print("✓ 推理测试通过")
print("\n模型已就绪，可以启动服务:")
print("  python pose_server.py")
EOF
```

---

## 启动服务

```bash
conda activate mmpose_gpu
cd ~/code/tenclip/pose
python pose_server.py
```

访问 http://localhost:5000 体验 GPU 加速的实时姿态检测！

---

## 关于从其他环境平移 PyTorch

### 可行性分析

✅ **可行，但有条件**：

1. **相同 Python 版本**：tenclip 是 Python 3.12，mmpose_gpu 是 Python 3.10
   - ❌ 直接复制不可行（Python 版本不同）
   - ✅ 可以用相同的安装源重新安装

2. **相同 CUDA 版本**：tenclip 的 torch 是 cu130
   - ✅ mmpose_gpu 也可以用 cu130
   - ✅ 或者用 cu121（兼容 cu130）

### 推荐方案

**不建议直接复制**，而是使用相同的安装源：

```bash
# 在 mmpose_gpu 环境中
conda activate mmpose_gpu

# 使用与 tenclip 相同的 PyTorch 版本
pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu130

# 或者用 conda（更简单）
conda install pytorch torchvision torchaudio pytorch-cuda=13.0 -c pytorch -c nvidia -y
```

### 为什么不推荐直接复制？

1. **Python 版本不同**：3.12 vs 3.10，二进制不兼容
2. **依赖路径问题**：硬编码的路径会失效
3. **符号链接问题**：conda 环境使用符号链接管理
4. **可能的版本冲突**：其他依赖可能不匹配

### 如果一定要复用已下载的文件

可以复用 conda 的缓存：

```bash
# conda 会自动复用已下载的包缓存
# 只要包名和版本相同，不会重复下载
conda install pytorch=2.11.0 -c pytorch -c nvidia
```

---

## 一键安装脚本（完整版）

```bash
#!/bin/bash
conda activate mmpose_gpu

echo "安装 PyTorch..."
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y

echo "配置 pip 镜像源..."
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

echo "安装 MMPose 依赖..."
pip install -U openmim
pip install mmengine mmcv mmdet mmpose
pip install chumpy json_tricks matplotlib munkres opencv-python pillow scipy xtcocotools flask flask-cors

echo "验证安装..."
python -c "import torch, mmpose; print(f'\n✓ PyTorch {torch.__version__}, CUDA {torch.cuda.is_available()}, MMPose {mmpose.__version__}')"

echo "安装完成！运行: python pose_server.py"
```

---

## 故障排除

### PyTorch 下载慢

使用国内镜像（但注意可能不是最新版本）：

```bash
# 使用清华 PyTorch 镜像
pip install torch torchvision torchaudio -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### MMCV 安装失败

```bash
# 直接用 pip 安装（跳过 mim）
pip install mmcv

# 或从源码编译
MMCV_WITH_OPS=1 pip install mmcv --no-binary mmcv
```

### GPU 不可用

```bash
# 检查驱动
nvidia-smi

# 检查 PyTorch CUDA
python -c "import torch; print(torch.version.cuda); print(torch.cuda.is_available())"

# 重新安装正确的 CUDA 版本
conda install pytorch pytorch-cuda=12.1 -c pytorch -c nvidia -y
```

---

## 总结

推荐安装顺序：
1. ✅ 使用 **conda 安装 PyTorch**（最简单）
2. ✅ 使用 **pip + 清华源**安装其他包（最快）
3. ✅ 验证所有依赖
4. ✅ 测试模型推理
5. ✅ 启动服务

完成后，你将拥有一个完整的 GPU 加速 MMPose 环境！🚀
