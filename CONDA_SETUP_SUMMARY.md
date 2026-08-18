# Conda 环境部署总结

## 📋 为你创建了什么

### 📦 三个核心文件

1. **`requirements_rtmpose_cpu.txt`** (40+ 行)
   - 完整的依赖列表
   - CPU 优化版本
   - 包含 mmpose/torch/flask 等所有依赖
   - 可重复使用

2. **`setup_conda_env.py`** (300+ 行)
   - Python 跨平台脚本（推荐）
   - 自动化整个部署过程
   - 支持自定义环境名称和 Python 版本
   - Linux/Mac/Windows WSL 都能用

3. **`setup_conda_env.sh`** (250+ 行)
   - Bash 快速脚本
   - Linux/Mac 优化
   - 与 Python 脚本功能相同

### 📚 完整指南

**`CONDA_ENV_SETUP_GUIDE.md`** (400+ 行)
- 详细的部署步骤
- 故障排查
- 环境维护
- 性能预期

---

## 🚀 立即使用

### 最快（一键部署）

```bash
# SSH 到云主机
ssh root@your-server-ip

# 进入项目
cd ~/tenclip

# 一键部署（5 分钟）
python setup_conda_env.py

# 启动服务
conda activate tenclip
cd pose && python pose_server_v2.py
```

### 完整流程（20 分钟）

```bash
# 1. 更新代码
cd ~/tenclip
git pull origin feature/pose

# 2. 创建环境（选一个方式）
python setup_conda_env.py              # 推荐
# 或
bash setup_conda_env.sh tenclip        # Bash 版本
# 或
conda create -n tenclip python=3.10 -y # 手动
conda activate tenclip
pip install -r requirements_rtmpose_cpu.txt

# 3. 验证
python -c "from mmpose.apis import MMPoseInferencer; print('✓')"

# 4. 启动
cd pose
python pose_server_v2.py

# 5. 验证服务
curl http://localhost:5000/api/health
```

---

## ✨ 脚本特点

### 自动化程度 ⭐⭐⭐⭐⭐

```
检查 conda ✓
创建环境 ✓
升级 pip ✓
安装依赖 ✓
验证安装 ✓
显示指南 ✓
```

### 聪明的地方

✅ **检测已有环境** - 如果环境存在，询问是否重建  
✅ **分步安装** - 避免超时或冲突  
✅ **清华源优化** - 国内下载 10 倍快  
✅ **完整验证** - 检查每个关键模块  
✅ **跨平台** - Python 脚本在任何系统都能用  

---

## 📊 包含的依赖

```
✓ Flask 3.1.3            (Web 框架)
✓ PyTorch 2.5.1 (CPU)    (深度学习)
✓ MMPose 1.3.2           (RTMpose 核心)
✓ MMCV 2.1.0             (MM 框架)
✓ MMDet 3.2.0            (目标检测)
✓ OpenCV 5.0.0           (图像处理)
✓ NumPy/SciPy            (数值计算)
✓ MediaPipe 0.10.14      (回退方案)
✓ 其他工具库 (pandas, matplotlib, etc)
```

---

## 🎯 使用场景

### 场景 1: 部署到新云主机

```bash
cd ~/tenclip
python setup_conda_env.py   # 15-25 分钟，一次性
conda activate tenclip
cd pose && python pose_server_v2.py
```

### 场景 2: 本地开发测试

```bash
python setup_conda_env.py
conda activate tenclip
# 开发、测试、调试
```

### 场景 3: 多机器部署

```bash
# 机器 A: 导出
conda activate tenclip
conda env export > tenclip.yml

# 机器 B: 导入
conda env create -f tenclip.yml
```

---

## ⏱️ 时间预期

| 操作 | 时间 |
|------|------|
| 检查 conda | <1 分钟 |
| 创建环境 | 1-2 分钟 |
| 安装 PyTorch | 5-10 分钟 |
| 安装 MMPose | 3-5 分钟 |
| 安装其他 | 2-3 分钟 |
| 验证 | <1 分钟 |
| **总计** | **15-25 分钟** |

之后启动服务只需：
```bash
conda activate tenclip && python pose_server_v2.py
```

---

## ✅ 验证清单

部署完成后，检查：

- [ ] 环境已创建
  ```bash
  conda env list | grep tenclip
  ```

- [ ] 依赖已安装
  ```bash
  conda activate tenclip
  python -c "import torch, mmpose, flask; print('✓')"
  ```

- [ ] RTMpose 可用
  ```bash
  python -c "from mmpose.apis import MMPoseInferencer; print('✓')"
  ```

- [ ] 服务可启动
  ```bash
  cd pose && python pose_server_v2.py
  ```

- [ ] API 可访问
  ```bash
  curl http://localhost:5000/api/health
  ```

---

## 📚 文件导航

```
tenclip/
├── requirements_rtmpose_cpu.txt      ← 依赖列表
├── setup_conda_env.py                ← Python 脚本（推荐）
├── setup_conda_env.sh                ← Bash 脚本
├── CONDA_ENV_SETUP_GUIDE.md          ← 完整指南
├── CONDA_SETUP_SUMMARY.md            ← 本文档
│
├── CPU_CLOUD_QUICK_FIX.md            (前面的 PyTorch 修复)
├── QUICK_INSTALL_CLOUD.md            (快速安装指南)
├── RTMPOSE_V2_DEPLOYMENT_GUIDE.md    (完整部署)
│
└── pose/
    ├── pose_server_v2.py             ← 后端服务
    ├── README_V2.md
    └── ...
```

---

## 🎯 推荐使用流程

### 本地开发环境（WSL/Linux）

```bash
# 第一次
python setup_conda_env.py

# 之后每次
conda activate tenclip
cd pose
python pose_server_v2.py
```

### 云主机部署

```bash
# SSH 连接
ssh root@your-server-ip

# 一次性部署（第一次）
cd ~/tenclip
python setup_conda_env.py    # 15-25 分钟

# 启动服务
conda activate tenclip
cd pose
nohup python pose_server_v2.py > pose.log 2>&1 &

# 后续只需
conda activate tenclip
cd pose
python pose_server_v2.py
```

---

## 💡 关键优势

vs 手动安装：
- ✅ **省时** - 一键自动化，省 30 分钟
- ✅ **无错** - 自动检测和验证，避免遗漏
- ✅ **可重复** - 相同的环境，任何机器
- ✅ **易维护** - requirements.txt 清晰，便于更新

vs 简单 pip install：
- ✅ **隔离** - 环境独立，不污染系统 Python
- ✅ **版本控制** - 精确版本，易于追踪
- ✅ **导出导入** - 环境可导出，便于复制
- ✅ **多版本** - 可同时维护多个环境

---

## 🚀 最终建议

**使用 `setup_conda_env.py`**

```bash
python setup_conda_env.py
```

这是最简单、最可靠的部署方式。

脚本会帮你：
1. ✅ 检查环境
2. ✅ 创建 Conda 环境
3. ✅ 安装所有依赖
4. ✅ 验证可用性
5. ✅ 提示后续步骤

---

**Now you have**：

✅ 完整的 requirements.txt  
✅ 自动化部署脚本（Python 和 Bash）  
✅ 详细的部署指南  
✅ 故障排查方案  
✅ 环境导出导入方法  

**Ready for production deployment!** 🚀
