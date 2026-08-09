# MMPose 项目功能总结

> 调研时间：2026-08-04  
> 项目地址：https://github.com/open-mmlab/mmpose  
> 文档：https://mmpose.readthedocs.io/

## 1. 项目简介

MMPose 是 OpenMMLab 推出的姿态分析开源工具箱，基于 PyTorch，支持多种人体姿态分析任务。

### 1.1 核心特性

- ✅ **多任务支持**：2D/3D 姿态估计、人脸/手部关键点、全身姿态、动物姿态
- ✅ **高性能**：SOTA 算法复现，更高精度和训练速度
- ✅ **模块化设计**：解耦框架，便于组合构建自定义模型
- ✅ **丰富数据集**：支持 COCO、MPII、Human3.6M 等 40+ 主流数据集
- ✅ **易部署**：支持 ONNX、TensorRT、ncnn、OpenVINO 等多种后端

## 2. 支持的任务类型

### 2.1 人体姿态估计

| 任务类型 | 关键点数 | 应用场景 | 代表算法 |
|---------|---------|---------|---------|
| **2D 人体姿态** | 17 (COCO) / 26 / 133 | 动作识别、视频分析 | RTMPose, HRNet, ViTPose |
| **3D 人体姿态** | 17 (3D) | 生物力学、AR/VR | VideoPose3D, SimpleBaseline3D |
| **全身姿态** | 133 (身体+手+脸) | AIGC、精细动作捕捉 | RTMPose-WholeBody, DWPose |
| **多人姿态** | - | 人群分析、体育赛事 | RTMO, RTMPose |

### 2.2 其他关键点任务

- **人脸关键点**：68/98 点，表情识别、人脸对齐
- **手部关键点**：21 点，手势识别、AR 交互
- **动物姿态**：马、猫、狗等，动物行为分析
- **服饰关键点**：时尚分析、虚拟试衣

## 3. RTMPose：实时姿态估计利器

### 3.1 性能指标

**RTMPose-m** 在 COCO 验证集上的表现：

| 指标 | 数值 |
|------|------|
| AP (COCO) | **75.8%** |
| CPU-FPS (i7-11700) | **90+ FPS** |
| GPU-FPS (GTX 1660 Ti) | **430+ FPS** |
| 移动端 (骁龙865) | **70+ FPS** @ 72.2% AP |

### 3.2 模型规格

| 模型 | AP | CPU-FPS | GPU-FPS | 参数量(M) | FLOPs(G) |
|------|----|---------|---------| ---------|----------|
| RTMPose-t | 68.5 | 300+ | 940+ | 3.34 | 0.36 |
| RTMPose-s | 72.2 | 200+ | 710+ | 5.47 | 0.68 |
| RTMPose-m | 75.8 | 90+ | 430+ | 13.59 | 1.93 |
| RTMPose-l | 76.5 | 50+ | 280+ | 27.66 | 4.16 |

### 3.3 部署优势

- 🚀 **多后端支持**：ONNX、TensorRT、ncnn、OpenVINO
- 🚀 **跨平台**：Linux、Windows、NVIDIA Jetson、ARM
- 🚀 **多语言 SDK**：Python、C++、C#、Java、Android

## 4. 是否能做实时关键点检测？

### ✅ **完全支持实时检测**

MMPose 特别是 **RTMPose** 专为实时应用设计：

#### 4.1 技术支撑

1. **高帧率推理**
   - CPU 上可达 90-300+ FPS（轻量模型）
   - GPU 上可达 430-940+ FPS
   - 移动端可达 70+ FPS

2. **Webcam 推理支持**
   ```bash
   # 摄像头实时推理示例
   python demo/inferencer_demo.py \
       --pose2d webcam \
       --vis-out-dir vis_results
   ```

3. **低延迟 Pipeline**
   - 检测 + 姿态估计端到端优化
   - 支持隔帧检测策略（默认5帧间隔）
   - 适配 CPU/GPU/移动端

#### 4.2 实时检测方案

**方案 A：Python + OpenCV + RTMPose**
```python
from mmpose.apis import MMPoseInferencer

# 初始化推理器
inferencer = MMPoseInferencer(
    pose2d='rtmpose-m',
    pose2d_weights='rtmpose-m_simcc-coco_pt-aic-coco_420e-256x192.pth',
    device='cuda:0'  # or 'cpu'
)

# Webcam 实时推理
for frame in webcam:
    results = inferencer(frame, show=True)
```

**方案 B：部署到 Web 端**
- MMDeploy + ONNX Runtime → Web Assembly
- TensorFlow.js / ONNX.js 浏览器推理
- MediaPipe Pose（Google 方案，浏览器原生）

**方案 C：移动端 App**
- ncnn + Android/iOS
- TensorFlow Lite
- CoreML (iOS)

## 5. 支持的算法（40+ 种）

### 5.1 经典算法
- DeepPose (CVPR'14)
- CPM (CVPR'16)
- Hourglass (ECCV'16)
- SimpleBaseline (ECCV'18)
- HRNet (CVPR'19)

### 5.2 SOTA 算法
- ViTPose (NeurIPS'22)
- RTMPose (2023) ⭐
- RTMO (2024) ⭐
- PoseAnything (2024)

### 5.3 3D 与视频
- VideoPose3D (CVPR'19)
- VoxelPose (ECCV'20)
- MHFormer (CVPR'22)

## 6. 数据集支持（40+ 个）

### 6.1 人体姿态
- **COCO** (ECCV'14)：最常用的 2D 姿态数据集
- **MPII** (CVPR'14)：单人姿态
- **Human3.6M** (TPAMI'14)：3D 姿态
- **CrowdPose** (CVPR'19)：密集人群

### 6.2 全身/细粒度
- **COCO-WholeBody** (ECCV'20)：133 关键点
- **Halpe** (CVPR'20)：26 关键点
- **UBody** (CVPR'23)：全身

### 6.3 专项任务
- **300W、WFLW**：人脸关键点
- **FreiHand、InterHand2.6M**：手部姿态
- **AP-10K、Animal-Pose**：动物姿态

## 7. 在网球场景的应用潜力

### 7.1 适合的任务

| 任务 | 方案 | 实时性 |
|------|------|--------|
| **击球动作分析** | RTMPose-m (17点) | ✅ 90+ FPS |
| **全身协调性评估** | RTMPose-WholeBody (133点) | ✅ 40+ FPS |
| **多人双打分析** | RTMO | ✅ 支持 |
| **3D 动作重建** | VideoPose3D | ⚠️ 后处理 |

### 7.2 技术栈建议

```
网球视频 → RTMDet (人体检测) → RTMPose (关键点) → 
  → 时序分析 (PoseC3D/ST-GCN) → 动作识别/纠错建议
```

### 7.3 与 VLM 结合

结合之前的 VLM 调研，可构建：
```
RTMPose 关键点 → 骨架序列 → VLM (LLaVA-Pose / KptLLM) 
  → 自然语言反馈（"引拍过低"、"重心偏后"）
```

## 8. 快速上手

### 8.1 安装

```bash
# 安装 PyTorch
pip install torch torchvision

# 安装 MMPose
pip install -U openmim
mim install mmengine
mim install mmcv
mim install mmdet  # 用于人体检测
mim install mmpose
```

### 8.2 Webcam 实时推理

```bash
cd mmpose

# 单人姿态
python demo/inferencer_demo.py \
    --pose2d rtmpose-m \
    --vis-out-dir vis_results \
    webcam

# 多人姿态
python demo/inferencer_demo.py \
    --pose2d rtmo-m \
    --vis-out-dir vis_results \
    webcam
```

### 8.3 视频文件推理

```bash
python demo/inferencer_demo.py \
    --pose2d rtmpose-m \
    --vis-out-dir vis_results \
    input_video.mp4
```

## 9. 部署方案

### 9.1 导出模型

```bash
# 使用 MMDeploy 导出 ONNX
mim download mmpose --config rtmpose-m_8xb256-420e_coco-256x192 --dest .

python tools/deployment/export_model.py \
    rtmpose-m_8xb256-420e_coco-256x192.py \
    rtmpose-m.pth \
    --output-file rtmpose-m.onnx
```

### 9.2 Web 端部署

```javascript
// 使用 ONNX Runtime Web
const session = await ort.InferenceSession.create('rtmpose-m.onnx');
const results = await session.run(inputTensor);
```

### 9.3 移动端部署

```bash
# Android (ncnn)
mim download mmpose --config rtmpose-m_8xb256-420e_coco-256x192
python tools/deployment/export_model.py \
    --backend ncnn \
    --output-file rtmpose-m.param
```

## 10. 性能优化建议

### 10.1 实时场景

- ✅ 使用 **RTMPose-t/s**（轻量模型）
- ✅ 开启 **隔帧检测**（每5帧检测一次）
- ✅ 使用 **TensorRT**（GPU）或 **ncnn**（移动端）
- ✅ 降低输入分辨率（256x192 → 192x144）

### 10.2 精度场景

- ✅ 使用 **RTMPose-l** 或 **ViTPose-h**
- ✅ 使用 **Flip Test**（左右翻转增强）
- ✅ 提高输入分辨率（384x288）
- ✅ 多帧时序后处理

## 11. 相关资源

- 📘 [官方文档](https://mmpose.readthedocs.io/)
- 🎮 [在线 Demo](https://openxlab.org.cn/apps/detail/mmpose/RTMPose)
- 💻 [GitHub 仓库](https://github.com/open-mmlab/mmpose)
- 📦 [模型下载](https://download.openmmlab.com/mmpose/)
- 🎬 [视频教程](https://space.bilibili.com/1293512903)

## 12. 前端 vs 后端方案对比

### 12.1 前端方案：MediaPipe Pose

**技术栈**：
- **开发者**: Google
- **版本**: @mediapipe/pose@0.5
- **运行环境**: 浏览器（WebAssembly + WebGL）
- **模型大小**: 6-8 MB
- **关键点**: 33 个（包含面部和手部）

**性能指标**：
```
FPS:      30-60（依赖设备）
延迟:     15-30ms
精度:     中等
资源占用:  低（浏览器 GPU）
```

**优势**：
- ✅ 零安装，浏览器直接运行
- ✅ 完全本地化，隐私保护
- ✅ 跨平台（桌面、移动端）
- ✅ 快速原型验证
- ✅ 关键点数量多（33 个）

**劣势**：
- ❌ 依赖 CDN，国内可能受限
- ❌ 性能受浏览器限制
- ❌ 精度低于专业模型
- ❌ 难以集成到后端流程

**CDN 加载**：
```html
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/control_utils@0.6/control_utils.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils@0.3/drawing_utils.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/pose.js"></script>
```

**模型配置**：
```javascript
pose.setOptions({
    modelComplexity: 1,        // 0-轻量, 1-标准, 2-精确
    smoothLandmarks: true,
    enableSegmentation: false,
    minDetectionConfidence: 0.5,
    minTrackingConfidence: 0.5
});
```

### 12.2 后端方案：MMPose RTMPose

**技术栈**：
- **开发者**: OpenMMLab
- **模型**: RTMPose 系列（t/s/m/l/x）
- **运行环境**: Python + PyTorch + GPU
- **模型大小**: 5-30 MB（依模型）
- **关键点**: 17 个（COCO 标准）

**性能指标（RTX 3060）**：
```
模型         FPS      延迟      显存      精度(AP)
RTMPose-t   150-200   5-7ms    ~1.5GB    68.5
RTMPose-s   100-150   7-10ms   ~2GB      72.2
RTMPose-m   80-120    10-12ms  ~2.5GB    75.8
RTMPose-l   60-90     12-15ms  ~3.5GB    76.5
```

**优势**：
- ✅ 高性能（GPU 加速）
- ✅ 高精度（COCO 76.5% AP）
- ✅ 完全本地化，无网络依赖
- ✅ 灵活部署（ONNX、TensorRT）
- ✅ 适合生产环境

**劣势**：
- ❌ 需要环境配置（Python + GPU）
- ❌ 部署复杂度高
- ❌ 需要服务器资源
- ❌ 关键点数量少（17 个）

**快速启动**：
```bash
conda activate mmpose_gpu
cd ~/code/tenclip/pose
python pose_server.py
# 访问 http://localhost:5000
```

### 12.3 方案对比矩阵

| 对比项 | MediaPipe Pose（前端） | RTMPose（后端 GPU） |
|--------|----------------------|-------------------|
| **部署难度** | ⭐ 极简（无需安装） | ⭐⭐⭐⭐ 复杂 |
| **FPS** | 30-60 | 80-120 (RTMPose-m) |
| **延迟** | 15-30ms | 10-12ms |
| **精度** | ⭐⭐⭐ 中 | ⭐⭐⭐⭐⭐ 高 |
| **关键点数** | 33 个 | 17 个 |
| **隐私性** | ⭐⭐⭐⭐⭐ 本地 | ⭐⭐⭐⭐⭐ 本地 |
| **网络依赖** | 需要（CDN） | 不需要 |
| **硬件要求** | 低 | 高（需要 GPU） |
| **适用环境** | 演示、移动端 | 生产、高精度 |
| **成本** | 免费 | GPU 硬件成本 |

### 12.4 使用场景推荐

#### 🎯 前端 MediaPipe Pose 适用场景

1. **快速原型验证**
   - 概念验证（POC）
   - 用户体验测试
   - 功能演示

2. **移动端应用**
   - 移动浏览器
   - 跨平台 Web App
   - 轻量级应用

3. **隐私敏感场景**
   - 个人健身 App
   - 医疗数据处理
   - 无服务器架构

4. **教育与科普**
   - 教学演示
   - 互动展示
   - 科普项目

#### 🎯 后端 RTMPose 适用场景

1. **生产环境**
   - 商业化产品
   - 企业级应用
   - SaaS 服务

2. **高性能需求**
   - 实时分析系统
   - 批量视频处理
   - 多路视频流

3. **高精度需求**
   - 体育动作分析（网球、高尔夫）
   - 生物力学研究
   - 医疗康复评估

4. **复杂场景**
   - 多人检测
   - 复杂背景
   - 遮挡处理

### 12.5 混合方案

对于网球分析项目，可以采用混合架构：

```
前端演示 (MediaPipe Pose)
    ↓
用户体验良好 → 升级
    ↓
后端分析 (RTMPose + GPU)
    ↓
详细报告 + 动作建议
```

**实现方式**：
1. 前端用 MediaPipe 提供即时反馈
2. 关键视频片段上传到后端
3. 后端用 RTMPose 精确分析
4. 生成专业报告

## 13. 结论

### ✅ **MMPose 完全支持实时关键点检测**

- **RTMPose** 系列模型专为实时应用设计
- CPU 可达 **90-300+ FPS**，GPU 可达 **430-940+ FPS**
- 支持 **Webcam、视频文件、RTSP 流** 等多种输入
- 提供完整的 **部署工具链**（ONNX、TensorRT、ncnn、Web）
- 适合网球等体育场景的 **动作分析与实时反馈**

### 推荐方案

**快速演示与原型**（前端）：
```
MediaPipe Pose (浏览器)
  → 30-60 FPS
  → 零安装、即开即用
  → 适合概念验证
```

**网球视频实时分析**（后端）：
```
RTMDet-nano (人体检测) + RTMPose-m (姿态) 
  → 80-120 FPS @ GPU (RTX 3060)
  → 适合实时教练反馈系统
```

**离线高精度分析**（后端）：
```
RTMDet-m + RTMPose-l + 时序平滑
  → COCO 76.5% AP
  → 适合动作细节纠错与生物力学分析
```

### 技术选型建议

| 需求 | 推荐方案 | 理由 |
|------|---------|------|
| 快速演示 | MediaPipe Pose | 零配置、快速上手 |
| 移动端 | MediaPipe Pose | 浏览器原生支持 |
| 生产环境 | RTMPose-m/l | 高性能、高精度 |
| 批量处理 | RTMPose + GPU | 并行处理能力强 |
| 实时反馈 | 混合方案 | 前端预览 + 后端分析 |
