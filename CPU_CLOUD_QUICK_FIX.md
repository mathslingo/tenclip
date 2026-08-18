# CPU 云主机快速修复指南

> 解决 PyTorch/MMCV 兼容性问题，启用 RTMpose

---

## 🎯 你有两个选择

### 选择 A: 继续用 MediaPipe（最简单）

```bash
# 当前已经可用了，什么都不用做
python pose_server_v2.py

# 检查
curl http://localhost:5000/api/health
```

**优点**：立即可用  
**缺点**：性能稍低（但 CPU 上差别不大）

---

### 选择 B: 修复 PyTorch，启用 RTMpose（推荐）

#### 最快方式：一键修复脚本

```bash
# Python 脚本（推荐）
python fix_pytorch_cpu.py

# 或 Bash 脚本
bash fix_pytorch_cpu.sh
```

脚本会：
1. ✅ 卸载旧 PyTorch
2. ✅ 安装 CPU 专用版本
3. ✅ 安装 mmcv/mmdet/mmpose
4. ✅ 验证 RTMpose

---

## 🚀 手动修复（如果脚本不行）

### 步骤 1: 卸载旧 PyTorch

```bash
pip uninstall torch torchvision torchaudio -y
```

### 步骤 2: 安装 CPU 版本

```bash
# 方式 A：从官方源（推荐）
pip install torch torchvision torchaudio

# 方式 B：从清华源（国内快）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  torch torchvision torchaudio
```

### 步骤 3: 验证 PyTorch

```bash
python -c "import torch; print('✓ PyTorch OK'); print('CUDA:', torch.cuda.is_available())"
```

### 步骤 4: 安装 MMPose

```bash
# 重要：用 pip 安装，不要用 mim（避免编译）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  mmcv mmdet mmpose
```

### 步骤 5: 验证 RTMpose

```bash
python -c "from mmpose.apis import MMPoseInferencer; print('✓ RTMpose OK')"
```

### 步骤 6: 启动服务

```bash
python pose_server_v2.py
```

---

## ❓ 常见问题

### Q: 修复后仍然报错？

**A**: 可能是编译问题。用预编译版本：

```bash
# 卸载所有相关包
pip uninstall mmcv mmdet mmpose torch -y

# 重新安装（完整的预编译包）
pip install mmcv-full mmdet mmpose \
  -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 修复后 RTMpose 加载失败？

**A**: MediaPipe 回退仍可用。检查：

```bash
curl http://localhost:5000/api/health

# 查看日志
tail -f pose.log
```

### Q: 修复需要多长时间？

**A**: 
- PyTorch 下载：5-10 分钟（~400MB）
- MMPose 等：5-10 分钟
- 总共：10-20 分钟

### Q: 云主机内存不足？

**A**: 使用轻量模型：

```bash
# 编辑 pose_server_v2.py 最后一行
init_models(model_size='s')  # 轻量版，推荐 CPU
```

---

## 📊 修复前后对比

### 修复前（当前）

```
✅ 后端运行（MediaPipe 回退）
✅ 小程序可用
⚠️ 性能：MediaPipe（较慢）
```

### 修复后

```
✅ 后端运行（RTMpose）
✅ 小程序可用
✅ 性能：RTMpose-s（快，推荐 CPU）
```

---

## 🎯 推荐步骤（CPU 云主机）

### 第 1 次（安装）

```bash
# 一键修复
python fix_pytorch_cpu.py

# 或手动
pip uninstall torch -y
pip install torch torchvision torchaudio
pip install mmcv mmdet mmpose
```

### 之后每次启动

```bash
# 选择模型大小（编辑 pose_server_v2.py）
init_models(model_size='s')  # s = 轻量（推荐 CPU）

# 启动
python pose_server_v2.py

# 后台运行
nohup python pose_server_v2.py > pose.log 2>&1 &
```

---

## ✅ 验证修复成功

### 标志 1: 服务启动

```
✓ rtmpose-s 模型加载成功
或
✓ MediaPipe Pose 加载成功（回退方案）

启动 Flask 服务...
访问地址: http://localhost:5000
```

### 标志 2: API 响应

```bash
curl http://localhost:5000/api/health

# 应该返回：
# {"status":"ok","model_loaded":true,"model_config":{"model_name":"rtmpose-s"},"gpu_info":{"available":false}}
```

### 标志 3: 小程序连接

打开小程序 → 发现 → 实时关键点检测 → RTMpose v2  
应该能看到实时检测结果

---

## 💡 性能优化（CPU 模式）

### 推荐配置

```python
# pose_server_v2.py

# 1. 使用轻量模型
init_models(model_size='s')

# 2. 调整推理间隔（如果觉得慢）
# 编辑 miniprogram/pages/pose-rtmpose/index.js
const INTERVAL_MS = 1000;  # 改为 1000ms（从 400ms）
```

### CPU 云主机预期性能

```
模型: rtmpose-s (轻量)
推理时间: 100-200ms
FPS: 5-10
内存: ~500MB
```

---

## 🚀 总结

| 选择 | 时间 | 复杂度 | 性能 |
|------|------|--------|------|
| 继续 MediaPipe | 0 | 简单 | 中等 |
| 修复 RTMpose | 15-20min | 简单 | 更好 |

**建议**：运行修复脚本，15 分钟后就能用更快的 RTMpose

```bash
python fix_pytorch_cpu.py
```

---

**Ready?** 🚀
