# RTMpose v2 云主机快速安装指南

> 一键安装 MMPose 并启动 RTMpose v2 实时检测服务

---

## 🚀 最快的方式（推荐）

### 方式 1: Python 脚本（跨平台，推荐）

```bash
# SSH 连接到云主机
ssh root@your-server-ip

# 进入项目目录
cd ~/tenclip/pose

# 运行安装脚本
python install_mmpose_cpu.py
```

**优点**：
- ✅ 跨平台（Linux、Mac、Windows WSL）
- ✅ 自动检测已有模块
- ✅ 智能安装缺失依赖
- ✅ 最终验证可用性
- ✅ 无需额外依赖

### 方式 2: Bash 脚本（Linux/Mac）

```bash
cd ~/tenclip/pose
bash install_mmpose_cpu.sh
```

---

## ⚡ 超快速（一键命令）

如果你的云主机已有基础 Python 环境：

```bash
ssh root@your-server-ip
cd ~/tenclip && git pull origin feature/pose && \
cd pose && python install_mmpose_cpu.py && \
python pose_server_v2.py
```

---

## 📋 分步详解

### 步骤 1: 更新代码

```bash
ssh root@your-server-ip
cd ~/tenclip

# 如果是首次克隆
git clone https://github.com/mathslingo/tenclip.git
cd tenclip
git checkout feature/pose

# 如果已有仓库，拉取最新
git fetch origin
git checkout feature/pose
git pull origin feature/pose
```

### 步骤 2: 创建 conda 环境（可选）

```bash
# 如果想要隔离环境（推荐）
conda create -n tenclip python=3.10 -y
conda activate tenclip
```

### 步骤 3: 安装 MMPose

```bash
cd ~/tenclip/pose

# Python 脚本安装（推荐）
python install_mmpose_cpu.py

# 或 Bash 脚本
bash install_mmpose_cpu.sh
```

**脚本会**：
1. ✅ 检查已有模块
2. ✅ 自动跳过已安装的包
3. ✅ 安装缺失的 mmpose/mmcv/mmdet
4. ✅ 最终验证 RTMpose 可用

### 步骤 4: 启动服务

#### 方式 A: 前台运行（测试用）

```bash
python pose_server_v2.py
```

输出应该显示：
```
✓ rtmpose-m 模型加载成功
✓ GPU 预热完成  (如果有 GPU)
预期性能: 80-120 FPS
或
✓ MediaPipe Pose 加载成功（回退方案）

启动 Flask 服务...
访问地址: http://localhost:5000
```

#### 方式 B: 后台运行（生产用）

```bash
# 简单后台运行
nohup python pose_server_v2.py > pose.log 2>&1 &

# 查看日志
tail -f pose.log

# 停止服务
pkill -f pose_server_v2
```

#### 方式 C: Systemd 服务（最佳）

```bash
# 参考 RTMPOSE_V2_DEPLOYMENT_GUIDE.md 配置 Systemd
sudo systemctl start tenclip-pose-v2
sudo systemctl enable tenclip-pose-v2
```

---

## 🎯 验证安装

### 检查服务是否运行

```bash
# 方式 1: 检查端口
lsof -i :5000
netstat -tln | grep 5000

# 方式 2: 健康检查 API
curl http://localhost:5000/api/health

# 应该返回：
# {"status":"ok","model_loaded":true,"model_config":{...},"gpu_info":{...}}
```

### 测试检测功能

```bash
# 使用 Web UI 测试
curl http://localhost:5000/

# 或用 curl 调用 API
curl -X POST http://localhost:5000/api/detect \
  -H "Content-Type: application/json" \
  -d '{
    "image": "<base64-encoded-image>",
    "confidence_threshold": 0.5,
    "return_visualization": true
  }'
```

---

## 🛠️ 常见问题

### Q: 安装时网络慢？

**A**: 已使用清华源，但如果仍然慢：

```bash
# 手动配置阿里源
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 或恢复官方源
pip config set global.index-url https://pypi.python.org/simple
```

### Q: 云主机没有 GPU，如何优化？

**A**: 已自动使用 CPU 模式。进一步优化：

```bash
# 1. 使用轻量模型
# 编辑 pose_server_v2.py，改：
# init_models(model_size='s')  # 轻量，推荐 CPU

# 2. 增加推理间隔（牺牲实时性换取稳定性）
# 编辑 pose-rtmpose/index.js
# const INTERVAL_MS = 1000;  // 改为 1000ms 而不是 400ms

# 3. 压缩图像分辨率
# 前端可以在上传前压缩图像
```

### Q: 启动时报 "Port 5000 is in use"？

**A**: 有程序占用端口 5000：

```bash
# 查看占用进程
lsof -i :5000

# 杀死进程
kill -9 <PID>

# 或用不同端口启动
# 编辑 pose_server_v2.py 最后：
# app.run(host='0.0.0.0', port=5001, ...)
```

### Q: MMPose 下载太慢？

**A**: 第一次启动会下载模型（~300MB），正常。之后会缓存：

```bash
# 模型缓存路径
~/.cache/mim/models/

# 预先下载模型（可选）
python -c "from mmpose.apis import MMPoseInferencer; MMPoseInferencer(pose2d='rtmpose-m')"
```

### Q: 云主机 Python 版本太低？

**A**: 需要 Python 3.8+：

```bash
# 检查版本
python --version

# 更新（如果使用 apt）
sudo apt-get update
sudo apt-get install python3.10 -y

# 或使用 conda 创建新环境
conda create -n tenclip python=3.10 -y
conda activate tenclip
```

---

## 📊 性能预期

### 有 GPU 的云主机

```
Model: rtmpose-m
GPU: V100/RTX3090
推理时间: 15-25ms
FPS: 40-65
显存占用: 3-4GB
```

### 无 GPU 的云主机（CPU 模式）

```
Model: rtmpose-s (轻量，推荐)
CPU: 8 核 16GB
推理时间: 100-200ms
FPS: 5-10
内存占用: 500MB-1GB
```

**CPU 上推荐用 `rtmpose-s`（轻量版），不要用 `rtmpose-l`**

---

## 🔧 配置选项

### 修改模型大小

编辑 `pose_server_v2.py` 最后一行：

```python
# 轻量版（推荐 CPU）- 最快，精度差点
init_models(model_size='s')

# 标准版 - 平衡（推荐 GPU）
init_models(model_size='m')

# 高精度版 - 最精准，最慢
init_models(model_size='l')
```

### 修改端口

编辑 `pose_server_v2.py` 最后：

```python
app.run(host='0.0.0.0', port=5000, debug=False)
# 改为
app.run(host='0.0.0.0', port=5001, debug=False)
```

### 配置 Nginx 反向代理（可选）

```nginx
server {
    listen 8000;
    
    location /pose/ {
        proxy_pass http://localhost:5000/;
        proxy_set_header Host $host;
        proxy_read_timeout 120s;
    }
}
```

---

## 📈 部署检查清单

部署完成后验证：

- [ ] 代码已拉取
  ```bash
  git log --oneline -1
  ```

- [ ] MMPose 已安装
  ```bash
  python -c "import mmpose; print(mmpose.__version__)"
  ```

- [ ] 服务已启动
  ```bash
  curl http://localhost:5000/api/health
  ```

- [ ] 防火墙已配置
  ```bash
  sudo ufw allow 5000/tcp
  ```

- [ ] 小程序可访问
  - 打开小程序 → 发现 → 实时关键点检测 → RTMpose v2
  - 应该能连接到后端

---

## 🚀 快速启动组合

### 本地开发环境

```bash
# 一次性安装（第一次）
python install_mmpose_cpu.py

# 之后每次启动
python pose_server_v2.py --size m
```

### 云主机生产环境

```bash
# SSH 连接
ssh root@your-server-ip

# 一次性部署
cd ~/tenclip && git pull && cd pose && \
python install_mmpose_cpu.py

# 启动服务（后台）
nohup python pose_server_v2.py > pose.log 2>&1 &

# 或用 Systemd
sudo systemctl start tenclip-pose-v2
```

### 容器部署（Docker，可选）

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .

# 安装依赖
RUN python install_mmpose_cpu.py

# 启动
CMD ["python", "pose_server_v2.py"]
```

---

## 📞 需要帮助？

| 问题 | 解决方案 |
|------|---------|
| 安装失败 | 运行 `python install_mmpose_cpu.py`，它会详细报告问题 |
| 启动报错 | 检查日志：`tail -f pose.log` |
| API 无法连接 | 检查防火墙和端口：`netstat -tln \| grep 5000` |
| 性能太慢 | 使用轻量模型：`init_models(model_size='s')` |
| 显存不足 | 用 CPU：删除 CUDA 环境变量或改编辑 pose_server_v2.py |

---

## ✅ 成功标志

安装完成标志：
```
✅ RTMpose v2 安装完成！
✅ Web UI: http://localhost:5000
✅ API: http://localhost:5000/api/detect
✅ 小程序可访问 RTMpose v2 页面
```

---

**Ready?** 
```bash
python install_mmpose_cpu.py && python pose_server_v2.py
```

🚀 Let's go!
