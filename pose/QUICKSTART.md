# 姿态检测环境快速配置（mmpose_gpu）

## 当前问题

`mmpose_gpu` 环境只有 Python 3.10，缺少所有依赖。

## 一键安装（推荐）

在 WSL 终端复制执行：

ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.    
torch 2.5.1 requires fsspec, which is not installed.
torch 2.5.1 requires sympy==1.13.1, but you have sympy 1.14.0 which is incompatible.

```bash
conda activate mmpose_gpu
cd ~/code/tenclip/pose

# 1. 基础依赖（Flask、OpenCV等）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  flask flask-cors opencv-python numpy pillow

# 2. PyTorch（用 pip 从官方源，自带 MKL，比 conda 快）
pip uninstall -y torch torchvision torchaudio  # 先清理
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 3. MMPose 完整版（分步安装，避免编译失败）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine

# mmcv 必须用 mim 安装（避免从源码编译）
mim install mmcv

# 其余组件
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  chumpy json_tricks matplotlib munkres scipy xtcocotools

# 4. 验证
python -c "import flask, torch, mmpose; print('✓ 全部就绪, GPU:', torch.cuda.is_available())"

# 5. 启动服务
python pose_server.py
```

## 分步说明

### 网络问题？

如果遇到 PyTorch 官方源连接超时，有两个选择：

**选择 1：先用 CPU 版本（推荐）**
```bash
# CPU 版本可以从清华源下载，下载量小
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 网络好的时候再升级
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**选择 2：conda 清华源**
```bash
# 配置清华源
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/pytorch/

# 安装（约 2GB）
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -y
```

### 步骤 1：基础依赖

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  flask flask-cors opencv-python numpy pillow
```

解决当前 `No module named 'flask'` 报错。

### 步骤 2：PyTorch

```bash
# 先清理旧版本
pip uninstall -y torch torchvision torchaudio

# 用 pip 从官方源安装（推荐）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 验证
python -c "import torch; print('✓ PyTorch:', torch.__version__, 'CUDA:', torch.cuda.is_available())"
```

**为什么用 pip 而不是 conda？**
- pip wheel 自带完整依赖（bundled MKL），避免依赖冲突
- 下载量更小（~800MB vs ~2GB）
- 安装更快

**为什么不用清华源？**
- PyTorch 官方不在清华源，必须用 `--index-url` 指定官方源

### 步骤 3：MMPose（分步安装）

```bash
# 3a. 安装 openmim 和 mmengine
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine

# 3b. ⚠️ mmcv 必须用 mim（不要用 pip！）
mim install mmcv

# 3c. 安装 mmdet、mmpose 和其他依赖
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  chumpy json_tricks matplotlib munkres scipy xtcocotools
```

**为什么 mmcv 必须用 mim？**
- `pip install mmcv` 会下载源码包（`.tar.gz`），尝试本地编译
- 编译需要 CUDA、setuptools、pkg_resources 等复杂依赖
- `mim install mmcv` 会自动下载预编译的 wheel，完全跳过编译

### 步骤 4：验证

```bash
# 检查所有关键模块
python << 'EOF'
import flask
import torch
import mmpose
print(f"✓ Flask:  {flask.__version__}")
print(f"✓ PyTorch: {torch.__version__}")
print(f"✓ CUDA:    {torch.cuda.is_available()}")
print(f"✓ GPU:     {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
print(f"✓ MMPose:  {mmpose.__version__}")
EOF
```

### 步骤 5：启动

```bash
python pose_server.py
```

访问 http://localhost:5000（或小程序配置的地址）

## 备选方案：MediaPipe

如果 MMPose 装不上或不需要 GPU：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mediapipe
python pose_server.py  # 会自动回退到 MediaPipe
```

## 常见问题

### Q: `No module named 'flask'`

A: 执行步骤 1

### Q: `No module named 'torch'`

A: 执行步骤 2（用 conda，不要用 pip + 清华源）

### Q: `No module named 'mmpose'`

A: 执行步骤 3

### Q: `ModuleNotFoundError: No module named 'pkg_resources'` (mmcv 安装时)

A: **不要用 pip 直接安装 mmcv！** 用 mim：
```bash
mim install mmcv
```

如果 mim 也报错，先安装 setuptools：
```bash
pip install --upgrade setuptools
mim install mmcv
```

### Q: `CUDA not available`

A: 
```bash
# 检查驱动
nvidia-smi

# 重装 PyTorch CUDA 版本
conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia -y
```

### Q: pip 下载慢

A: 确认已配置清华源（PyTorch 除外）：
```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

## 预期结果

安装完成后 `conda list` 应包含：

```
flask               3.x
opencv-python       4.x
torch               2.x+cu121
mmpose              1.x
mmcv                2.x
mmdet               3.x
```

耗时约 5-15 分钟（取决于网速和是否有缓存）。

## 相关文档

- `requirements.txt` - 依赖列表（含注释说明）
- `INSTALL_GUIDE.md` - 详细安装指南
- `INSTALL_REMAINING_STEPS.md` - 分步骤说明
- `pose_server.py` - 后端服务代码
