# Push 和部署总结

## 📋 当前状态

### Git 仓库信息

```
✅ 远程仓库: https://github.com/mathslingo/tenclip.git
✅ 当前分支: feature/pose
✅ 分支跟踪: origin/feature/pose
⏳ 待提交: 90+ 个修改文件，9 个新增文件
```

### 新增文件

```
pose/
├── pose_server_v2.py              (1500+ 行，后端核心)
├── start_rtmpose_v2.py            (300+ 行，启动脚本)
├── start_rtmpose_v2.sh            (150+ 行，Bash 脚本)
├── INDEX.md                       (文档导航)
├── README_V2.md                   (快速指南)
└── RTMPOSE_V2_GUIDE.md            (技术手册)

miniprogram/pages/pose-rtmpose/    (新模块)
├── index.js
├── index.wxml
├── index.wxss
└── index.json

根目录/
├── RTMPOSE_V2_IMPLEMENTATION_SUMMARY.md
├── RTMPOSE_V2_QUICK_REFERENCE.md
├── RTMPOSE_V2_DEPLOYMENT_GUIDE.md  (部署指南)
└── commit_and_push.sh              (推送脚本)
```

---

## 🚀 一键推送（推荐）

### 最简单的方式

```bash
cd ~/code/tenclip
bash commit_and_push.sh
```

这个脚本会：
1. ✅ 暂存所有修改和新文件
2. ✅ 显示即将提交的内容供审查
3. ✅ 要求确认
4. ✅ 提交到本地仓库
5. ✅ 推送到 GitHub
6. ✅ 显示推送结果

---

## 📝 手动推送步骤

### 1. 提交代码

```bash
cd ~/code/tenclip

# 添加所有修改
git add .

# 检查状态
git status

# 提交
git commit -m "feat: 实现 RTMpose v2 实时姿态检测系统"
```

### 2. 推送到 GitHub

```bash
git push origin feature/pose
```

### 3. 验证推送

```bash
# 查看远程分支
git log origin/feature/pose --oneline -5

# 或访问 GitHub
# https://github.com/mathslingo/tenclip/tree/feature/pose
```

---

## 🌐 云主机部署

### 快速部署（3 步）

#### 第 1 步: 更新代码

```bash
ssh root@你的服务器IP

cd ~/tenclip  # 或你的项目目录

# 更新到最新代码
git fetch origin
git checkout feature/pose
git pull origin feature/pose
```

#### 第 2 步: 安装依赖

```bash
cd ~/tenclip/pose

# 创建虚拟环境（如果还没有）
conda create -n tenclip python=3.10 -y
conda activate tenclip

# 安装依赖（选一种方式）

# 方式 A: 完整安装（推荐）
bash << 'EOF'
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  flask flask-cors opencv-python numpy pillow

pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu121

pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine
mim install mmcv
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose
EOF

# 方式 B: 快速安装（仅 RTMpose）
pip install flask flask-cors opencv-python numpy pillow torch mmpose
```

#### 第 3 步: 启动服务

```bash
# 方式 A: 直接启动（测试用）
python pose_server_v2.py

# 方式 B: 后台启动（推荐）
nohup python pose_server_v2.py > /var/log/pose_server.log 2>&1 &

# 方式 C: Systemd 服务（生产环境，见详细指南）
sudo systemctl start tenclip-pose-v2
```

#### 验证部署

```bash
# 检查服务
curl http://localhost:5000/api/health

# 查看日志
tail -f /var/log/pose_server.log
```

---

## 📚 详细指南

| 需求 | 文档 |
|------|------|
| **推送到 GitHub** | 本文档 (第一部分) |
| **云主机部署详解** | RTMPOSE_V2_DEPLOYMENT_GUIDE.md |
| **故障排查** | RTMPOSE_V2_DEPLOYMENT_GUIDE.md#故障排查 |
| **性能优化** | RTMPOSE_V2_DEPLOYMENT_GUIDE.md#生产环境配置 |
| **监控和日志** | RTMPOSE_V2_DEPLOYMENT_GUIDE.md#监控和日志 |

---

## 🎯 推荐流程

### 情景 1: 本地开发完成，推送到 GitHub

```bash
# 1. 在本地测试
cd ~/code/tenclip
python pose/start_rtmpose_v2.py --size m

# 打开小程序，验证功能

# 2. 提交和推送
bash commit_and_push.sh

# 3. 检查 GitHub
# https://github.com/mathslingo/tenclip/tree/feature/pose
```

### 情景 2: 在云主机部署

```bash
# 1. SSH 连接到服务器
ssh root@your-server-ip

# 2. 更新代码
cd ~/tenclip
git fetch origin
git checkout feature/pose
git pull

# 3. 安装依赖和启动
cd pose
conda activate tenclip
python pose_server_v2.py &

# 4. 配置 Nginx（可选）
# 参考部署指南
```

### 情景 3: 生产环境（完整部署）

```bash
# 1. 推送代码
bash commit_and_push.sh

# 2. 更新云主机
ssh root@your-server-ip
cd ~/tenclip && git pull

# 3. 按照 RTMPOSE_V2_DEPLOYMENT_GUIDE.md 完整部署：
# - Systemd service 或 Supervisor
# - Nginx 反向代理
# - 性能监控
# - 日志轮转
```

---

## ✨ 关键检查清单

### 推送前

- [ ] 在本地测试无误
  ```bash
  python ~/code/tenclip/pose/start_rtmpose_v2.py
  curl http://localhost:5000/api/health
  ```

- [ ] 检查要推送的文件
  ```bash
  git status
  git diff --cached --stat
  ```

- [ ] 确保有网络连接
  ```bash
  ping github.com
  ```

### 推送时

- [ ] 使用有意义的提交信息
- [ ] 确认分支为 `feature/pose`

### 推送后

- [ ] 验证 GitHub 上的代码
  ```bash
  git log origin/feature/pose --oneline -1
  ```

### 部署前

- [ ] 下载最新代码
  ```bash
  git pull origin feature/pose
  ```

- [ ] 验证文件完整性
  ```bash
  [ -f pose/pose_server_v2.py ] && echo "✓" || echo "✗"
  ```

- [ ] 检查依赖
  ```bash
  python -c "import torch, mmpose; print('✓')"
  ```

### 部署后

- [ ] 服务启动成功
  ```bash
  systemctl status tenclip-pose-v2
  ```

- [ ] API 健康检查
  ```bash
  curl http://localhost:5000/api/health
  ```

- [ ] 小程序可访问
  ```
  打开小程序 → 发现 → 实时关键点检测 → RTMpose v2
  ```

---

## 🔗 常用命令速查

### Git 相关

```bash
# 查看状态
git status

# 查看修改
git diff

# 查看日志
git log --oneline

# 添加文件
git add .

# 提交
git commit -m "message"

# 推送
git push origin feature/pose

# 拉取最新
git pull origin feature/pose

# 检查远程
git remote -v
```

### 云主机部署

```bash
# 连接服务器
ssh root@your-ip

# 更新代码
git pull origin feature/pose

# 启动服务
python pose_server_v2.py  # 前台
nohup python pose_server_v2.py &  # 后台
systemctl start tenclip-pose-v2  # Systemd

# 查看日志
tail -f /var/log/pose_server.log
journalctl -u tenclip-pose-v2 -f

# 停止服务
systemctl stop tenclip-pose-v2
```

---

## 💡 常见问题

### Q: Push 时提示"没有权限"？

**A**: 检查 GitHub 权限
```bash
# 测试 SSH 连接
ssh -T git@github.com

# 或配置 HTTP 认证
git config --global credential.helper store
```

### Q: 云主机上依赖安装失败？

**A**: 使用清华源
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <package>

# 或编辑 ~/.pip/pip.conf
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 部署后 RTMpose 模型加载缓慢？

**A**: 这是正常的，首次加载要下载模型（~300MB）
```bash
# 后续会缓存在 ~/.cache/mim/models
ls ~/.cache/mim/models/
```

### Q: 如何切换模型大小？

**A**: 编辑启动命令
```bash
# 轻量（快速）
python pose_server_v2.py  # 默认 m
# 编辑 pose_server_v2.py 最后一行
# init_models(model_size='s')

# 高精度（精准）
# init_models(model_size='l')
```

---

## 📊 部署对比

| 方式 | 复杂度 | 可靠性 | 性能 | 推荐场景 |
|------|--------|--------|------|---------|
| 直接运行 | ⭐ 简单 | ⭐⭐ | ⭐⭐⭐ | 测试 |
| Systemd | ⭐⭐ 中等 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 标准部署 |
| Supervisor | ⭐⭐ 中等 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 多进程 |
| Gunicorn | ⭐⭐⭐ 复杂 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 生产环境 |

**推荐**：Systemd + Nginx（简单可靠，性能足够）

---

## 🎯 下一步行动

### 立即执行

1. **推送代码**
   ```bash
   cd ~/code/tenclip
   bash commit_and_push.sh
   ```

2. **验证 GitHub**
   - 打开 https://github.com/mathslingo/tenclip/tree/feature/pose
   - 确认所有文件已推送

### 后续部署

1. **准备云主机**
   - 确保有 Python 3.8+ 和 CUDA 环境
   - 或联系服务商配置环境

2. **部署 RTMpose v2**
   - 按照 RTMPOSE_V2_DEPLOYMENT_GUIDE.md 部署
   - 或使用快速 3 步部署

3. **配置生产环境**
   - Systemd service 或 Supervisor
   - Nginx 反向代理
   - 监控和日志

---

## 📞 获得帮助

遇到问题？查看：

1. **推送问题** - 本文档的"常见问题"部分
2. **部署问题** - RTMPOSE_V2_DEPLOYMENT_GUIDE.md#故障排查
3. **功能问题** - pose/README_V2.md#常见问题
4. **API 文档** - pose/RTMPOSE_V2_GUIDE.md

---

## ✅ 成功标志

推送成功 ✅
```
✓ GitHub 上有新提交
✓ feature/pose 分支已更新
✓ 所有 RTMpose v2 文件已提交
```

部署成功 ✅
```
✓ 云主机上运行着 pose_server_v2.py
✓ curl http://server-ip:5000/api/health 返回 ok
✓ 小程序能访问 RTMpose v2 页面
```

---

**准备好了吗？** 

```bash
cd ~/code/tenclip
bash commit_and_push.sh
```

🚀 让我们开始吧！
