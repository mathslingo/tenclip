# MediaPipe 前端版加载问题解决方案

## 问题现象

打开 `realtime_pose_detection.html` 后卡在"正在加载 MediaPipe Pose 模型..."

## 原因分析

1. **CDN 访问受限**：MediaPipe 的 CDN（jsdelivr.net）在国内访问不稳定
2. **网络连接慢**：首次加载需要下载 6-8 MB 模型文件
3. **浏览器限制**：某些浏览器或插件阻止跨域脚本

## 快速解决方案 ⭐

### 方案 1：使用后端服务（强烈推荐）

**优势：**
- ✅ 不依赖外部 CDN
- ✅ 性能更好（GPU 加速）
- ✅ 更稳定可靠
- ✅ 可离线使用

**启动步骤：**

```bash
cd /home/hayden/code/tenclip/pose

# 快速启动（使用 MediaPipe 后端）
pip install flask flask-cors opencv-python numpy pillow mediapipe
python3 pose_server.py

# 打开浏览器访问
http://localhost:5000
```

**完整安装（使用 MMPose，性能更好）：**

```bash
# 1. 安装基础依赖
pip install flask flask-cors opencv-python numpy pillow

# 2. 安装 PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# 3. 安装 MMPose
pip install -U openmim
mim install mmengine mmcv mmdet mmpose

# 4. 启动服务
python3 pose_server.py
```

### 方案 2：修复纯前端版

如果坚持使用纯前端版，尝试以下步骤：

#### 步骤 1：检查网络

```bash
# 测试 CDN 连接
curl -I https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/pose.js

# 如果超时或失败，说明 CDN 不可达
```

#### 步骤 2：使用科学上网

- 启用 VPN/代理工具
- 刷新页面（Ctrl+F5 或 Cmd+Shift+R）
- 等待 1-2 分钟让资源加载

#### 步骤 3：清除缓存

1. 打开浏览器开发者工具（F12）
2. 切换到 Network 标签
3. 勾选"Disable cache"
4. 刷新页面
5. 查看哪些文件加载失败

#### 步骤 4：更换浏览器

- Chrome/Edge（推荐）
- Firefox
- Safari（macOS）

### 方案 3：本地部署 MediaPipe（高级）

如果需要离线使用纯前端版：

```bash
# 1. 下载 MediaPipe 库到本地
cd pose
mkdir -p mediapipe-local
cd mediapipe-local

# 2. 下载文件（需要科学上网或在网络好的环境）
wget https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/pose.js
wget https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js
wget https://cdn.jsdelivr.net/npm/@mediapipe/control_utils@0.6/control_utils.js
wget https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils@0.3/drawing_utils.js

# 3. 下载模型文件
wget https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/pose_landmark_full.tflite
wget https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/pose_landmark_lite.tflite
wget https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/pose_landmark_heavy.tflite

# 4. 修改 HTML，使用本地文件
# （需要手动编辑 realtime_pose_detection.html）
```

## 各方案对比

| 方案 | 加载速度 | 稳定性 | 性能 | 部署难度 |
|------|---------|--------|------|---------|
| **后端服务 + MMPose** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **后端服务 + MediaPipe** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| **纯前端 + 科学上网** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| **纯前端 + 本地文件** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

## 推荐流程

```
遇到加载问题
    ↓
首选：使用后端服务
    ├─ 快速版：pip install mediapipe + python3 pose_server.py
    └─ 完整版：安装 MMPose + python3 pose_server.py
    ↓
如果必须用纯前端
    ├─ 科学上网后刷新
    ├─ 更换浏览器尝试
    └─ 下载本地文件部署
```

## 浏览器控制台诊断

打开浏览器开发者工具（F12），查看 Console 和 Network 标签：

### 正常情况：
```
页面加载完成，准备初始化 MediaPipe Pose
✓ MediaPipe Pose 模型加载完成
```

### 异常情况及解决：

**1. ERR_CONNECTION_TIMED_OUT**
```
原因：CDN 连接超时
解决：使用后端服务或科学上网
```

**2. Mixed Content 错误**
```
原因：HTTPS 页面加载 HTTP 资源
解决：确保所有资源都是 HTTPS，或使用 HTTP 打开页面
```

**3. CORS 错误**
```
原因：跨域资源访问被阻止
解决：使用后端服务，或通过 HTTP 服务器打开（python -m http.server）
```

**4. pose.js 404 Not Found**
```
原因：CDN 文件不存在或版本错误
解决：已在新版 HTML 中修复版本号
```

## 已应用的修复

最新版 `realtime_pose_detection.html` 已包含：

✅ 超时检测（10秒后提示）
✅ 错误友好提示
✅ CDN 版本锁定（避免不兼容）
✅ 加载失败自动提示切换到后端
✅ 详细的诊断信息

## 测试步骤

1. **测试后端服务**

```bash
cd pose
python3 pose_server.py
# 访问 http://localhost:5000
# 点击"启动检测"
```

2. **测试纯前端**

```bash
# 方法 1：直接打开
双击 realtime_pose_detection.html

# 方法 2：HTTP 服务器
python -m http.server 8080
# 访问 http://localhost:8080/realtime_pose_detection.html
```

3. **查看加载日志**

- 打开 F12 开发者工具
- 切换到 Console 标签
- 观察加载进度和错误信息

## 常见问题

### Q: 为什么后端服务更推荐？

A: 
- 不依赖外部 CDN，加载更快
- GPU 加速，性能是前端的 2-5 倍
- 支持多人检测、自定义模型
- 可离线使用，更稳定

### Q: 后端服务需要什么配置？

A:
- **最低**：Python 3.8+，2GB 内存，CPU
- **推荐**：Python 3.9+，8GB 内存，NVIDIA GPU
- **依赖**：见 `requirements.txt`

### Q: 纯前端版有什么限制？

A:
- 需要稳定的网络连接
- 首次加载需要下载模型文件
- 性能受浏览器限制
- 不支持多人检测

## 获取帮助

如果问题仍未解决：

1. 查看 `BACKEND_GUIDE.md` 获取详细的后端服务文档
2. 检查浏览器控制台的完整错误信息
3. 尝试不同的网络环境
4. 使用后端服务作为备选方案

## 总结

**最佳实践：** 直接使用后端服务（`pose_server.py`），跳过 CDN 加载问题，享受更好的性能和稳定性。

```bash
# 一行命令解决所有问题
cd pose && pip install flask opencv-python numpy pillow mediapipe && python3 pose_server.py
```
