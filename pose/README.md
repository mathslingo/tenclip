# 姿态估计实时检测项目

本目录包含 MMPose 项目分析与实时关键点检测演示。

## 📁 文件说明

### 1. `mmpose_summary.md`
MMPose 项目的完整功能总结文档，包括：
- 项目简介与核心特性
- 支持的任务类型（2D/3D 姿态、人脸、手部、全身、动物等）
- RTMPose 实时姿态估计工具
- 性能指标与部署方案
- **实时检测可行性分析**
- 在网球场景的应用建议

### 2. `realtime_pose_detection.html`
基于 MediaPipe Pose 的实时人体关键点检测网页，特性：
- ✅ **浏览器原生运行**，无需后端服务器
- ✅ **调用本地摄像头**进行实时检测
- ✅ **33 个关键点检测**（含手部和脸部）
- ✅ **骨架连接可视化**
- ✅ **实时 FPS 显示**
- ✅ **可调节模型参数**（复杂度、置信度阈值等）
- ✅ **截图保存功能**

### 3. `pose_server.py` ⭐ 新增
基于 MMPose RTMPose 的后端服务，特性：
- ✅ **高性能**：GPU 可达 80-120 FPS
- ✅ **自动降级**：MMPose 不可用时回退到 MediaPipe
- ✅ **REST API**：支持图像检测接口
- ✅ **内置演示页面**：访问 http://localhost:5000 即可使用
- ✅ **灵活部署**：支持 CPU/GPU，可扩展到生产环境

### 4. `start_server.sh` / `start_server.ps1`
一键启动脚本（Linux/macOS 和 Windows）：
- 自动检查依赖
- 提供依赖安装向导
- 启动后端服务

### 5. `BACKEND_GUIDE.md`
后端服务完整使用指南：
- 快速启动教程
- 依赖安装说明
- API 接口文档
- 性能优化建议
- 常见问题解答

### 6. `VLM_POSE_ESTIMATION_SURVEY.md`
VLM（视觉语言模型）与姿态估计的交叉研究综述。

### 7. `mmpose/`
MMPose 开源项目仓库（Git submodule）。

## 🚀 快速开始

### 方案 A：后端服务版（推荐，高性能）⭐

使用 MMPose RTMPose 后端，性能更强：

```bash
cd pose

# Linux/macOS
bash start_server.sh

# Windows
powershell -ExecutionPolicy Bypass -File start_server.ps1

# 或直接运行
python3 pose_server.py
```

启动后访问：`http://localhost:5000`

**优势：**
- ✅ GPU 加速：80-120 FPS（GTX 1660 Ti）
- ✅ 更高精度：RTMPose 专业级关键点检测
- ✅ 可扩展：支持多人检测、自定义模型

### 方案 B：纯前端版（快速体验）

使用 MediaPipe Pose 浏览器版，无需安装：

**方法 1：直接打开**
```bash
cd pose
# 双击 realtime_pose_detection.html
# 或使用命令行：
start realtime_pose_detection.html  # Windows
open realtime_pose_detection.html   # macOS
xdg-open realtime_pose_detection.html  # Linux
```

**方法 2：通过 HTTP 服务器**
```bash
cd pose
python -m http.server 8080
# 访问：http://localhost:8080/realtime_pose_detection.html
```

**优势：**
- ✅ 零安装：浏览器直接运行
- ✅ 隐私友好：本地处理，不上传数据
- ✅ 快速启动：2-3 秒即可使用

## 🎮 功能演示

### 关键点可视化
- **红色点**：头部关键点（鼻子、眼睛、耳朵、嘴）
- **青色点**：上肢关键点（肩膀、肘部、手腕、手指）
- **黄色点**：下肢关键点（髋部、膝盖、脚踝、脚）
- **绿色线**：骨架连接

### 可调参数
- **模型复杂度**：
  - 轻量 (Lite)：速度最快，精度较低
  - 标准 (Full)：平衡速度与精度（推荐）
  - 高精度 (Heavy)：精度最高，速度较慢

- **检测置信度**：调整关键点显示的最小置信度阈值
- **跟踪置信度**：调整跟踪算法的置信度阈值
- **关键点大小**：调整可视化的点大小

## 📊 性能对比

### MediaPipe Pose（网页版）
- **关键点数**：33 个（身体 + 手部 + 脸部）
- **FPS**：30-60 FPS（CPU），60-120 FPS（GPU）
- **延迟**：< 50ms
- **优势**：浏览器原生，无需安装，隐私友好
- **适用**：快速原型、教育演示、简单应用

### MMPose RTMPose（Python 后端）
- **关键点数**：17/26/133 个（可选）
- **FPS**：90-940 FPS（取决于模型和硬件）
- **延迟**：< 20ms
- **优势**：更高精度，可自定义，支持多人
- **适用**：生产环境、复杂场景、科研项目

## 🔧 MMPose 本地部署

如果需要更高性能或自定义功能，可以使用 MMPose：

### 安装
```bash
# 1. 安装依赖
pip install torch torchvision
pip install -U openmim
mim install mmengine mmcv mmdet mmpose

# 2. 克隆项目（如果还没有）
cd pose
git clone https://github.com/open-mmlab/mmpose.git
cd mmpose
```

### Webcam 实时推理
```bash
# 单人姿态检测
python demo/inferencer_demo.py \
    --pose2d rtmpose-m \
    --vis-out-dir vis_results \
    webcam

# 多人姿态检测
python demo/inferencer_demo.py \
    --pose2d rtmo-m \
    --vis-out-dir vis_results \
    webcam
```

### 视频文件处理
```bash
python demo/inferencer_demo.py \
    --pose2d rtmpose-m \
    --vis-out-dir vis_results \
    input_video.mp4
```

## 💡 应用场景

### 网球场景
- **动作分析**：击球姿态评估
- **教学辅助**：实时动作纠正提示
- **训练记录**：关键帧提取与对比
- **生物力学分析**：关节角度计算

### 其他场景
- 健身动作指导
- 舞蹈动作捕捉
- 康复训练评估
- 游戏/AR 交互
- 视频内容审核

## 📝 技术栈

### 网页版
- **MediaPipe Pose**：Google 开源的姿态估计模型
- **JavaScript**：前端交互逻辑
- **Canvas API**：关键点可视化
- **WebRTC**：摄像头访问

### MMPose 版
- **PyTorch**：深度学习框架
- **OpenMMLab**：计算机视觉工具生态
- **MMDeploy**：模型部署工具
- **ONNX/TensorRT**：推理加速

## 🌐 在线资源

- [MMPose 官方文档](https://mmpose.readthedocs.io/)
- [MediaPipe Pose 文档](https://google.github.io/mediapipe/solutions/pose.html)
- [RTMPose 在线 Demo](https://openxlab.org.cn/apps/detail/mmpose/RTMPose)
- [MMPose GitHub](https://github.com/open-mmlab/mmpose)

## ⚠️ 注意事项

### 隐私与安全
- 网页版在浏览器本地运行，**不上传任何视频数据**
- MediaPipe 模型从 CDN 加载，首次使用需要网络连接
- 建议在本地网络环境下使用

### 浏览器兼容性
- ✅ Chrome/Edge 80+
- ✅ Firefox 75+
- ✅ Safari 14+
- ⚠️ 移动浏览器可能性能受限

### 性能优化
- 关闭不必要的浏览器标签页
- 使用独立显卡（如有）
- 降低摄像头分辨率（如需要）
- 选择合适的模型复杂度

## 📧 反馈与贡献

如有问题或建议，欢迎反馈！

## 📄 许可证

- 网页演示代码：MIT License
- MMPose 项目：Apache 2.0 License
- MediaPipe：Apache 2.0 License
