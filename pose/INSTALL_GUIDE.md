# MMPose GPU 环境安装指南

## 环境要求

- WSL2 Ubuntu
- NVIDIA RTX 3060 (12GB VRAM)
- CUDA 12.1 或更高
- Conda/Miniconda

## 快速安装 ⭐

### 方式 1：一键安装脚本（推荐）

```bash
cd ~/code/tenclip/pose

# 运行安装脚本
bash setup_mmpose_env.sh
```

脚本会自动：
1. 创建 `mmpose_gpu` conda 环境（Python 3.10）
2. 安装 PyTorch + CUDA 12.1
3. 按照 mmpose 官方 requirements 安装所有依赖
4. 验证安装是否成功

### 方式 2：手动安装

```bash
# 1. 创建环境
conda create -n mmpose_gpu python=3.10 -y
conda activate mmpose_gpu

# 2. 配置镜像源（可选，加速下载）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 安装 PyTorch (CUDA 12.1)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 4. 安装 OpenMMLab 工具
pip install -U openmim
mim install mmengine
mim install "mmcv>=2.0.1"
mim install "mmdet>=3.0.0"
mim install "mmpose>=1.0.0"

# 5. 安装 MMPose 依赖
pip install chumpy json_tricks matplotlib munkres opencv-python pillow scipy xtcocotools

# 6. 安装 Flask 后端
pip install flask flask-cors

# 7. 验证安装
python -c "import torch, mmpose; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'MMPose: {mmpose.__version__}')"
```

## 启动服务

```bash
conda activate mmpose_gpu
cd ~/code/tenclip/pose
python pose_server.py
```

访问 http://localhost:5000

## 性能预期

| 模型 | FPS | 延迟 | 显存 |
|------|-----|------|------|
| RTMPose-t | 150-200 | 5-7ms | ~1.5GB |
| RTMPose-s | 100-150 | 7-10ms | ~2GB |
| RTMPose-m | 80-120 | 10-12ms | ~2.5GB |
| RTMPose-l | 60-90 | 12-15ms | ~3.5GB |

## 依赖说明

基于 mmpose 官方 requirements:

### Build Dependencies
- numpy
- torch>=1.8

### Runtime Dependencies
- chumpy
- json_tricks
- matplotlib
- munkres
- opencv-python
- pillow
- scipy
- torchvision
- xtcocotools>=1.12

### OpenMMLab Dependencies
- mmengine
- mmcv>=2.0.1
- mmdet>=3.0.0
- mmpose>=1.0.0

### Backend Dependencies
- flask
- flask-cors

## 故障排除

### Q: mim install 报错 `ImpImporter`

A: Python 3.12 兼容性问题，使用 Python 3.10（脚本已配置）

### Q: CUDA 版本不匹配

A: 使用 PyTorch CUDA 12.1 版本，兼容 CUDA 13.0

### Q: mmcv 编译失败

A: 使用 `mim install mmcv` 会自动下载预编译版本

### Q: GPU 不可用

A: 检查：
```bash
nvidia-smi  # 确认驱动正常
python -c "import torch; print(torch.cuda.is_available())"
```

### Q: 显存不足

A: 在 `pose_server.py` 中使用更小的模型（rtmpose-s）

## 环境管理

```bash
# 激活环境
conda activate mmpose_gpu

# 查看已安装包
pip list | grep mm

# 更新 MMPose
mim install --upgrade mmpose

# 删除环境
conda deactivate
conda env remove -n mmpose_gpu
```

## 相关文件

- `setup_mmpose_env.sh` - 自动安装脚本
- `pose_server.py` - Flask 后端服务
- `start_gpu_server.sh` - 服务启动脚本
- `gpu_config.py` - GPU 优化配置
- `GPU_GUIDE.md` - GPU 使用指南

## 参考

- MMPose 官方文档: https://mmpose.readthedocs.io/
- OpenMMLab: https://github.com/open-mmlab
- PyTorch 安装: https://pytorch.org/get-started/locally/
