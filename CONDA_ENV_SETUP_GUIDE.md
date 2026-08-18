# Conda 环境部署指南（RTMpose v2）

> 用 Conda + requirements.txt 快速部署 RTMpose v2 到云主机

---

## 🎯 快速开始

### 方式 1: Python 脚本（推荐，跨平台）

```bash
# SSH 连接到云主机
ssh root@your-server-ip

# 进入项目目录
cd ~/tenclip

# 运行部署脚本
python setup_conda_env.py
```

### 方式 2: Bash 脚本（Linux/Mac）

```bash
cd ~/tenclip
bash setup_conda_env.sh tenclip
```

### 方式 3: 手动操作（最自由）

```bash
# 1. 创建环境
conda create -n tenclip python=3.10 -y

# 2. 激活环境
conda activate tenclip

# 3. 安装依赖
pip install -r requirements_rtmpose_cpu.txt

# 4. 验证
python -c "from mmpose.apis import MMPoseInferencer; print('✓ OK')"
```

---

## 📋 包含的文件

| 文件 | 用途 |
|------|------|
| `requirements_rtmpose_cpu.txt` | 依赖列表（CPU 优化） |
| `setup_conda_env.py` | Python 部署脚本（推荐） |
| `setup_conda_env.sh` | Bash 部署脚本 |
| `CONDA_ENV_SETUP_GUIDE.md` | 本指南 |

---

## 🚀 部署步骤

### 第 1 步: 克隆/更新代码

```bash
ssh root@your-server-ip
cd ~

# 首次克隆
git clone https://github.com/mathslingo/tenclip.git
cd tenclip
git checkout feature/pose

# 或更新现有仓库
cd ~/tenclip
git fetch origin
git checkout feature/pose
git pull origin feature/pose
```

### 第 2 步: 创建 Conda 环境

**推荐：用脚本自动化**

```bash
# 一键创建（包括所有依赖）
python setup_conda_env.py

# 或指定环境名称
python setup_conda_env.py --name tenclip --python 3.10
```

脚本会自动：
1. ✅ 检查 conda
2. ✅ 创建 Python 3.10 环境
3. ✅ 安装所有依赖（mmpose, torch, flask 等）
4. ✅ 验证安装
5. ✅ 显示后续步骤

### 第 3 步: 激活环境并验证

```bash
conda activate tenclip

# 验证关键模块
python -c "import torch, mmpose, flask; print('✓ All OK')"
```

### 第 4 步: 启动服务

```bash
cd ~/tenclip/pose

# 前台运行（测试用）
python pose_server_v2.py

# 后台运行（生产用）
nohup python pose_server_v2.py > pose.log 2>&1 &

# 验证
curl http://localhost:5000/api/health
```

---

## 📊 脚本做什么

### `setup_conda_env.py` / `setup_conda_env.sh`

```
[1/5] 检查 conda
    ├─ 验证 conda 已安装
    └─ 显示版本信息

[2/5] 创建 conda 环境
    ├─ 创建 Python 3.10 环境（名为 tenclip）
    ├─ 如果环境已存在，询问是否删除
    └─ 确保干净的环境

[3/5] 初始化环境
    ├─ 升级 pip/setuptools/wheel
    └─ 配置清华源（加速下载）

[4/5] 安装依赖
    ├─ PyTorch (torch, torchvision, torchaudio)
    ├─ MMPose (mmengine, mmcv, mmdet, mmpose)
    ├─ 计算库 (numpy, scipy, sklearn)
    ├─ 图像处理 (opencv, pillow)
    ├─ Web 框架 (flask, flask-cors)
    ├─ 回退方案 (mediapipe)
    └─ 其他工具

[5/5] 验证安装
    ├─ 检查核心模块版本
    ├─ 测试 RTMpose 可用性
    ├─ 检查 GPU 状态
    └─ 显示最终状态
```

---

## 🔧 requirements.txt 详解

### 核心依赖

```
Flask==3.1.3              # Web 框架
torch==2.5.1              # 深度学习框架（CPU 版本）
mmpose==1.3.2             # RTMpose 模型
```

### 为什么是这些版本？

- **PyTorch 2.5.1 (CPU)**: 最新稳定版本，CPU 优化
- **mmpose 1.3.2**: 最新稳定，支持 RTMpose
- **mmcv 2.1.0**: 与 mmpose 1.3.2 兼容
- **mmdet 3.2.0**: mmpose 依赖

### 环境优化

- ✅ **CPU 专用**: 使用 PyTorch CPU 版本，避免 GPU 兼容性问题
- ✅ **清华源**: 配置国内加速源，下载 10 倍快
- ✅ **MediaPipe 回退**: 如果 RTMpose 加载失败，自动用 MediaPipe

---

## 💻 云主机环境预检查

在部署前，确保云主机有：

```bash
# 1. Python 环境
python3 --version  # 需要 3.8+

# 2. Conda 环境（如果还没有，安装 Miniconda）
conda --version

# 3. 充足的存储空间
df -h  # 至少需要 5GB 空闲空间

# 4. 网络连接
ping github.com
```

---

## 📈 预期部署时间

| 步骤 | 时间 | 说明 |
|------|------|------|
| 检查 conda | <1 分钟 | 快速 |
| 创建环境 | 1-2 分钟 | 快速 |
| 安装 PyTorch | 5-10 分钟 | 最慢（~400MB） |
| 安装 MMPose | 3-5 分钟 | 中等 |
| 安装其他 | 2-3 分钟 | 快速 |
| 验证 | <1 分钟 | 快速 |
| **总计** | **15-25 分钟** | 一次性 |

---

## ✅ 验证部署成功

### 标志 1: 环境创建

```bash
conda env list | grep tenclip
# 应该显示 tenclip 环境存在
```

### 标志 2: 依赖安装

```bash
conda activate tenclip
python -c "import torch, mmpose, flask; print('✓')"
# 应该打印 ✓
```

### 标志 3: RTMpose 可用

```bash
python -c "from mmpose.apis import MMPoseInferencer; print('✓')"
# 应该打印 ✓
```

### 标志 4: 服务启动

```bash
cd ~/tenclip/pose
python pose_server_v2.py
# 应该显示：
# ✓ RTMpose 模型加载成功
# 或
# ✓ MediaPipe Pose 加载成功（回退方案）
# 启动 Flask 服务...
# 访问地址: http://localhost:5000
```

---

## 🔄 环境维护

### 导出环境（用于复制到其他机器）

```bash
conda activate tenclip
conda env export > tenclip.yml

# 其他机器恢复
conda env create -f tenclip.yml
```

### 更新依赖

```bash
conda activate tenclip
pip install --upgrade -r requirements_rtmpose_cpu.txt
```

### 删除环境

```bash
conda env remove -n tenclip
```

---

## 🐛 故障排查

### Q: conda 不存在？

```bash
# 安装 Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 激活
source ~/.bashrc
```

### Q: 环境创建失败？

```bash
# 清理 conda 缓存
conda clean --all -y

# 重试
python setup_conda_env.py
```

### Q: 依赖安装超时？

```bash
# 切换源
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 或恢复官方源
pip config set global.index-url https://pypi.python.org/simple
```

### Q: RTMpose 加载失败但 MediaPipe 可用？

```bash
# 不影响使用，服务已自动回退到 MediaPipe
curl http://localhost:5000/api/health
# 应该返回 {"status":"ok"}
```

---

## 🎯 使用场景

### 场景 1: 开发环境

```bash
# 一键部署
python setup_conda_env.py

# 激活
conda activate tenclip

# 开发、测试
cd pose && python pose_server_v2.py
```

### 场景 2: 生产环境

```bash
# 一键部署
python setup_conda_env.py

# 后台运行
nohup python pose_server_v2.py > pose.log 2>&1 &

# 或用 Systemd（见 RTMPOSE_V2_DEPLOYMENT_GUIDE.md）
```

### 场景 3: 多机器部署

```bash
# 机器 1: 导出环境
conda env export > tenclip.yml

# 机器 2: 导入环境
conda env create -f tenclip.yml
```

---

## 📚 相关文档

| 文档 | 用途 |
|------|------|
| **CONDA_ENV_SETUP_GUIDE.md** | 本文件，环境部署 |
| CPU_CLOUD_QUICK_FIX.md | PyTorch 兼容性修复 |
| QUICK_INSTALL_CLOUD.md | 快速安装指南 |
| RTMPOSE_V2_DEPLOYMENT_GUIDE.md | 完整部署（Systemd 等） |

---

## 🚀 总结

**一句话**：用 conda + requirements.txt 部署是最佳实践

**三步完成**：
```bash
git pull origin feature/pose      # 1. 拉取代码
python setup_conda_env.py         # 2. 部署环境
cd pose && python pose_server_v2.py  # 3. 启动服务
```

**时间投入**：15-25 分钟（一次性）

**之后维护**：
```bash
conda activate tenclip            # 激活环境
python pose_server_v2.py          # 启动服务
```

---

**Ready?**

```bash
python setup_conda_env.py
```

Let's deploy RTMpose v2! 🚀
