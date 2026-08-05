# MMPose 实时姿态估计服务

## 快速启动

### Linux / macOS

```bash
cd pose

# 方法 1：使用启动脚本（推荐）
bash start_server.sh

# 方法 2：直接运行
python3 pose_server.py
```

### Windows

```powershell
cd pose

# 方法 1：使用启动脚本（推荐）
powershell -ExecutionPolicy Bypass -File start_server.ps1

# 方法 2：直接运行
python pose_server.py
```

## 依赖安装

### 完整版（MMPose，推荐）

```bash
# 1. 安装 PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# 2. 安装 MMPose
pip install -U openmim
mim install mmengine
mim install mmcv
mim install mmdet
mim install mmpose

# 3. 安装 Web 框架
pip install flask flask-cors opencv-python numpy pillow
```

### 轻量版（MediaPipe，快速开始）

```bash
# 基础依赖
pip install flask flask-cors opencv-python numpy pillow

# MediaPipe（备选方案）
pip install mediapipe
```

## 使用说明

### 1. 启动服务

运行后会自动：
- 加载 MMPose RTMPose 模型（或 MediaPipe）
- 启动 Flask 服务器（默认端口 5000）
- 打开浏览器访问演示页面

```
🚀 服务已启动: http://localhost:5000
📊 健康检查: http://localhost:5000/health
🎨 演示页面: http://localhost:5000
```

### 2. 访问演示页面

在浏览器中打开：`http://localhost:5000`

1. 点击 **"启动检测"** 按钮
2. 授予摄像头权限
3. 实时查看关键点检测结果

### 3. API 接口

#### 健康检查

```bash
curl http://localhost:5000/health
```

响应：
```json
{
  "status": "ok",
  "model_loaded": true,
  "backend": "MMPose",
  "device": "GPU"
}
```

#### 图像检测

```bash
curl -X POST http://localhost:5000/detect \
  -H "Content-Type: application/json" \
  -d '{
    "image": "data:image/jpeg;base64,/9j/4AAQ..."
  }'
```

响应：
```json
{
  "keypoints": [
    {"id": 0, "x": 320.5, "y": 240.2, "confidence": 0.95},
    ...
  ],
  "num_people": 1,
  "inference_time_ms": 45.2,
  "fps": 22.1,
  "image": "base64_encoded_result_image"
}
```

## 性能优化

### GPU 加速

确保安装了 CUDA 版本的 PyTorch：

```bash
# 检查 CUDA 是否可用
python -c "import torch; print(torch.cuda.is_available())"

# 如果返回 False，重新安装 CUDA 版本
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### 模型选择

在 `pose_server.py` 中修改模型：

```python
# 轻量级（速度快）
pose_model = MMPoseInferencer(pose2d='rtmpose-t')

# 标准版（平衡）
pose_model = MMPoseInferencer(pose2d='rtmpose-m')

# 高精度（精度高）
pose_model = MMPoseInferencer(pose2d='rtmpose-l')
```

### 降低分辨率

修改 HTML 中的摄像头配置：

```javascript
const stream = await navigator.mediaDevices.getUserMedia({ 
    video: { width: 640, height: 480 }  // 降低分辨率提升速度
});
```

## 常见问题

### Q: 模型加载失败

**A:** 确保安装了所有依赖：

```bash
# 检查 MMPose 版本
python -c "import mmpose; print(mmpose.__version__)"

# 重新安装
mim install mmpose --force-reinstall
```

### Q: 摄像头无法访问

**A:** 
- 检查浏览器权限设置
- 确保摄像头未被其他程序占用
- 使用 HTTPS 或 localhost（HTTP 在某些浏览器中会被阻止）

### Q: FPS 过低

**A:**
- 使用轻量级模型（rtmpose-t）
- 降低输入分辨率
- 启用 GPU 加速
- 关闭浏览器其他标签页

### Q: 显存不足

**A:**
```python
# 在 pose_server.py 开头添加
import torch
torch.cuda.set_per_process_memory_fraction(0.5)  # 限制使用 50% 显存
```

## 开发模式

启用 Flask 调试模式：

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python3 pose_server.py
```

## 生产部署

### 使用 Gunicorn（推荐）

```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:5000 pose_server:app
```

### 使用 Docker

```dockerfile
FROM python:3.9

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt
RUN mim install mmpose

EXPOSE 5000
CMD ["python", "pose_server.py"]
```

## 性能基准

### MMPose RTMPose-m

| 硬件 | FPS | 延迟 |
|------|-----|------|
| i7-11700 (CPU) | 15-20 | 50-65 ms |
| GTX 1660 Ti (GPU) | 80-120 | 8-12 ms |
| RTX 3090 (GPU) | 200+ | 5 ms |

### MediaPipe Pose

| 硬件 | FPS | 延迟 |
|------|-----|------|
| CPU | 25-35 | 30-40 ms |
| GPU | 50-80 | 15-20 ms |

## 许可证

- 后端代码：MIT License
- MMPose：Apache 2.0 License
- MediaPipe：Apache 2.0 License
