"""
实时姿态估计后端服务
基于 MMPose RTMPose 模型
优化：NVIDIA GPU 加速

依赖安装：
pip install flask flask-cors opencv-python numpy pillow
pip install torch torchvision  # 确保 CUDA 版本
pip install -U openmim
mim install mmengine mmcv mmdet mmpose

启动服务（GPU）：
conda activate tenclip
bash start_gpu_server.sh

或直接运行：
conda activate tenclip
CUDA_VISIBLE_DEVICES=0 python pose_server.py

API 端点：
- GET  /: 返回演示页面
- GET  /health: 健康检查 + GPU 信息
- POST /detect: 接收图像，返回关键点
- GET  /gpu_info: 获取详细 GPU 信息
"""

from flask import Flask, request, jsonify, Response, render_template_string
from flask_cors import CORS
import cv2
import numpy as np
import base64
import json
import time
from io import BytesIO
from PIL import Image
import os
import sys

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局变量
pose_model = None
detector_model = None
model_loaded = False
gpu_available = False
gpu_info = {}

def check_gpu():
    """检查 GPU 状态"""
    global gpu_available, gpu_info
    
    try:
        import torch
        
        gpu_available = torch.cuda.is_available()
        
        if gpu_available:
            gpu_info = {
                'available': True,
                'device_count': torch.cuda.device_count(),
                'current_device': torch.cuda.current_device(),
                'device_name': torch.cuda.get_device_name(0),
                'cuda_version': torch.version.cuda,
                'total_memory_gb': round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
            }
            
            # 设置 CUDA 优化
            torch.backends.cudnn.benchmark = True  # 自动优化卷积算法
            torch.backends.cudnn.enabled = True
            
            print(f"✓ GPU 检测成功: {gpu_info['device_name']}")
            print(f"  显存: {gpu_info['total_memory_gb']} GB")
            print(f"  CUDA: {gpu_info['cuda_version']}")
        else:
            gpu_info = {'available': False, 'reason': 'CUDA not available'}
            print("⚠ GPU 不可用，将使用 CPU")
            
    except ImportError:
        gpu_info = {'available': False, 'reason': 'PyTorch not installed'}
        print("⚠ PyTorch 未安装")
    except Exception as e:
        gpu_info = {'available': False, 'reason': str(e)}
        print(f"⚠ GPU 检测失败: {e}")

def init_models():
    """初始化 MMPose 模型（GPU 优化版）"""
    global pose_model, detector_model, model_loaded
    
    # 先检查 GPU
    check_gpu()
    
    try:
        from mmpose.apis import MMPoseInferencer
        
        # 根据显存选择最佳模型
        if gpu_available and gpu_info.get('total_memory_gb', 0) >= 10:
            model_name = 'rtmpose-l'  # 3060 12GB 可以跑 large 模型
            print(f"使用高精度模型: {model_name}")
        elif gpu_available and gpu_info.get('total_memory_gb', 0) >= 6:
            model_name = 'rtmpose-m'
            print(f"使用标准模型: {model_name}")
        else:
            model_name = 'rtmpose-s'
            print(f"使用轻量模型: {model_name}")
        
        device = 'cuda:0' if gpu_available else 'cpu'
        print(f"\n正在加载 {model_name} 到 {device}...")
        
        # 初始化推理器
        pose_model = MMPoseInferencer(
            pose2d=model_name,
            pose2d_weights=None,  # 自动下载
            device=device
        )
        
        model_loaded = True
        print(f"✓ {model_name.upper()} 模型加载成功")
        
        if gpu_available:
            # 预热 GPU
            print("预热 GPU...")
            dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
            _ = pose_model(dummy_img, return_vis=False)
            print("✓ GPU 预热完成")
            
            # 显示预期性能
            perf = {
                'rtmpose-t': '150-200 FPS',
                'rtmpose-s': '100-150 FPS',
                'rtmpose-m': '80-120 FPS',
                'rtmpose-l': '60-90 FPS',
            }
            print(f"\n预期性能: {perf.get(model_name, 'N/A')} @ RTX 3060")
        
    except Exception as e:
        print(f"✗ MMPose 加载失败: {e}")
        print("正在回退到 MediaPipe...")
        try:
            init_mediapipe()
        except Exception as e2:
            print(f"✗ MediaPipe 加载失败: {e2}")
            print("所有模型加载失败，请检查依赖")

def init_mediapipe():
    """回退方案：使用 MediaPipe"""
    global pose_model, model_loaded

    try:
        import mediapipe as mp
        
        # 兼容 MediaPipe 0.10.x 和 1.0+
        try:
            # MediaPipe 0.10.x
            mp_pose = mp.solutions.pose
            pose_model = mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            print("✓ MediaPipe Pose 加载成功 (v0.10)")
        except AttributeError:
            # MediaPipe 1.0+ 新 API
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            
            base_options = python.BaseOptions(
                model_asset_path='pose_landmarker.task'  # 需要下载模型文件
            )
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.VIDEO
            )
            pose_model = vision.PoseLandmarker.create_from_options(options)
            print("✓ MediaPipe Pose 加载成功 (v1.0+)")
        
        model_loaded = True

    except ImportError as e:
        print(f"MediaPipe 未安装或版本不兼容: {e}")
        print("推荐安装: pip install mediapipe==0.10.14")
        raise

def is_cuda_available():
    """检查是否有 CUDA（兼容性函数）"""
    return gpu_available

def decode_base64_image(base64_string):
    """解码 base64 图像"""
    # 移除 data URL 前缀
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    img_data = base64.b64decode(base64_string)
    img = Image.open(BytesIO(img_data))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def encode_image_to_base64(image):
    """编码图像为 base64"""
    _, buffer = cv2.imencode('.jpg', image)
    return base64.b64encode(buffer).decode('utf-8')

def detect_pose_mmpose(image):
    """使用 MMPose 检测姿态"""
    try:
        # MMPose 推理
        results = pose_model(image, return_vis=True)
        
        # 提取结果
        keypoints = []
        if results['predictions'] and len(results['predictions']) > 0:
            pred = results['predictions'][0]
            if 'keypoints' in pred:
                kpts = pred['keypoints']
                scores = pred.get('keypoint_scores', np.ones(len(kpts)))
                
                for i, (kpt, score) in enumerate(zip(kpts, scores)):
                    keypoints.append({
                        'id': i,
                        'x': float(kpt[0]),
                        'y': float(kpt[1]),
                        'confidence': float(score)
                    })
        
        # 获取可视化图像
        vis_image = results.get('visualization', [None])[0]
        if vis_image is None:
            vis_image = image
        
        return {
            'keypoints': keypoints,
            'num_people': len(results['predictions']),
            'image': encode_image_to_base64(vis_image)
        }
        
    except Exception as e:
        print(f"MMPose 检测出错: {e}")
        return {'error': str(e), 'keypoints': []}

def detect_pose_mediapipe(image):
    """使用 MediaPipe 检测姿态"""
    try:
        # 转换为 RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # MediaPipe 推理
        results = pose_model.process(image_rgb)
        
        keypoints = []
        if results.pose_landmarks:
            for i, landmark in enumerate(results.pose_landmarks.landmark):
                keypoints.append({
                    'id': i,
                    'x': landmark.x * image.shape[1],
                    'y': landmark.y * image.shape[0],
                    'confidence': landmark.visibility
                })
        
        # 绘制关键点
        vis_image = draw_keypoints(image.copy(), keypoints)
        
        return {
            'keypoints': keypoints,
            'num_people': 1 if keypoints else 0,
            'image': encode_image_to_base64(vis_image)
        }
        
    except Exception as e:
        print(f"MediaPipe 检测出错: {e}")
        return {'error': str(e), 'keypoints': []}

def draw_keypoints(image, keypoints, radius=5):
    """在图像上绘制关键点"""
    for kpt in keypoints:
        if kpt['confidence'] > 0.5:
            x, y = int(kpt['x']), int(kpt['y'])
            cv2.circle(image, (x, y), radius, (0, 255, 0), -1)
            cv2.circle(image, (x, y), radius + 2, (255, 255, 255), 2)
    return image

@app.route('/')
def index():
    """返回演示页面"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/health')
def health():
    """健康检查 + GPU 信息"""
    backend = 'MMPose' if 'MMPoseInferencer' in str(type(pose_model)) else 'MediaPipe' if pose_model else 'None'
    
    response = {
        'status': 'ok' if model_loaded else 'error',
        'model_loaded': model_loaded,
        'backend': backend,
        'device': 'GPU' if gpu_available else 'CPU',
        'gpu_info': gpu_info
    }
    
    return jsonify(response)

@app.route('/gpu_info')
def get_gpu_info():
    """获取详细 GPU 信息"""
    if not gpu_available:
        return jsonify({'available': False, 'message': 'GPU 不可用'})
    
    try:
        import torch
        
        detailed_info = {
            **gpu_info,
            'torch_version': torch.__version__,
            'memory_allocated_gb': round(torch.cuda.memory_allocated(0) / 1024**3, 3),
            'memory_reserved_gb': round(torch.cuda.memory_reserved(0) / 1024**3, 3),
            'max_memory_allocated_gb': round(torch.cuda.max_memory_allocated(0) / 1024**3, 3),
        }
        
        return jsonify(detailed_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect', methods=['POST'])
def detect():
    """检测单张图像"""
    if not model_loaded:
        return jsonify({'error': '模型未加载'}), 500
    
    try:
        data = request.get_json()
        
        if 'image' not in data:
            return jsonify({'error': '缺少 image 字段'}), 400
        
        # 解码图像
        image = decode_base64_image(data['image'])
        
        # 检测姿态
        start_time = time.time()
        
        if 'MMPoseInferencer' in str(type(pose_model)):
            result = detect_pose_mmpose(image)
        else:
            result = detect_pose_mediapipe(image)
        
        inference_time = (time.time() - start_time) * 1000  # ms
        
        result['inference_time_ms'] = round(inference_time, 2)
        result['fps'] = round(1000 / inference_time, 1)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"检测出错: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webcam')
def webcam():
    """Webcam 流式检测（SSE）"""
    def generate():
        cap = cv2.VideoCapture(0)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 检测
            if 'MMPoseInferencer' in str(type(pose_model)):
                result = detect_pose_mmpose(frame)
            else:
                result = detect_pose_mediapipe(frame)
            
            # 发送结果
            yield f"data: {json.dumps(result)}\n\n"
            
            time.sleep(0.03)  # 30 FPS
        
        cap.release()
    
    return Response(generate(), mimetype='text/event-stream')

# HTML 模板
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>实时姿态估计 - MMPose GPU 加速</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
            color: #fff;
        }
        .header { text-align: center; margin-bottom: 30px; }
        h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .subtitle { font-size: 1.1em; opacity: 0.9; }
        .container {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 1200px;
            width: 100%;
        }
        .controls { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
        button {
            padding: 12px 24px;
            font-size: 16px;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover { transform: translateY(-2px); }
        .video-container {
            position: relative;
            max-width: 800px;
            margin: 0 auto;
            border-radius: 12px;
            overflow: hidden;
            background: #000;
        }
        #video, #canvas { width: 100%; display: block; }
        #resultImage { width: 100%; display: none; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
            color: #333;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-label { font-size: 0.9em; color: #666; margin-bottom: 5px; }
        .stat-value { font-size: 1.8em; font-weight: 700; color: #667eea; }
        .status { margin: 20px 0; padding: 15px; border-radius: 8px; color: #333; text-align: center; }
        .status.loading { background: #fff3cd; }
        .status.ready { background: #d4edda; }
        .status.error { background: #f8d7da; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎾 实时姿态估计</h1>
        <p class="subtitle">MMPose RTMPose GPU 加速 | NVIDIA RTX 3060</p>
    </div>

    <div class="container">
        <div id="status" class="status loading">正在检查后端状态...</div>
        
        <div class="controls">
            <button id="startBtn" class="btn-primary">🎥 启动检测</button>
            <button id="stopBtn" class="btn-primary" disabled>⏹️ 停止</button>
            <button id="screenshotBtn" class="btn-primary">📸 截图</button>
            <button id="gpuInfoBtn" class="btn-primary" onclick="showGPUInfo()">🎮 GPU 信息</button>
        </div>

        <div class="video-container">
            <video id="video" autoplay playsinline></video>
            <canvas id="canvas" style="display:none;"></canvas>
            <img id="resultImage">
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">实时帧率 (FPS)</div>
                <div class="stat-value" id="fps">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">推理耗时 (ms)</div>
                <div class="stat-value" id="latency">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">检测人数</div>
                <div class="stat-value" id="peopleCount">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">关键点数量</div>
                <div class="stat-value" id="keypointsCount">0</div>
            </div>
        </div>
    </div>

    <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const resultImage = document.getElementById('resultImage');
        let isRunning = false;
        let animationId = null;

        // 检查后端状态
        fetch('/health')
            .then(r => r.json())
            .then(data => {
                const status = document.getElementById('status');
                if (data.status === 'ok') {
                    const gpuText = data.device === 'GPU' ? 
                        ` | GPU: ${data.gpu_info?.device_name || 'NVIDIA'} (${data.gpu_info?.total_memory_gb || '?'} GB)` : 
                        '';
                    status.className = 'status ready';
                    status.textContent = `✓ 后端就绪 | 模型: ${data.backend} | 设备: ${data.device}${gpuText}`;
                } else {
                    status.className = 'status error';
                    status.textContent = '✗ 后端未就绪';
                }
            })
            .catch(err => {
                const status = document.getElementById('status');
                status.className = 'status error';
                status.textContent = '✗ 无法连接到后端服务';
            });

        async function startDetection() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { width: 1280, height: 720 } 
                });
                video.srcObject = stream;
                video.style.display = 'block';
                resultImage.style.display = 'none';
                
                isRunning = true;
                document.getElementById('startBtn').disabled = true;
                document.getElementById('stopBtn').disabled = false;
                
                detectFrame();
            } catch (err) {
                alert('无法访问摄像头: ' + err.message);
            }
        }

        async function detectFrame() {
            if (!isRunning) return;
            
            // 捕获当前帧
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0);
            
            const imageData = canvas.toDataURL('image/jpeg', 0.8);
            
            // 发送到后端
            try {
                const response = await fetch('/detect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: imageData })
                });
                
                const result = await response.json();
                
                // 更新统计
                document.getElementById('fps').textContent = result.fps || 0;
                document.getElementById('latency').textContent = result.inference_time_ms || 0;
                document.getElementById('peopleCount').textContent = result.num_people || 0;
                document.getElementById('keypointsCount').textContent = result.keypoints?.length || 0;
                
                // 显示结果图像
                if (result.image) {
                    resultImage.src = 'data:image/jpeg;base64,' + result.image;
                    resultImage.style.display = 'block';
                    video.style.display = 'none';
                }
                
            } catch (err) {
                console.error('检测失败:', err);
            }
            
            // 继续下一帧
            animationId = requestAnimationFrame(detectFrame);
        }

        function stopDetection() {
            isRunning = false;
            if (animationId) {
                cancelAnimationFrame(animationId);
            }
            if (video.srcObject) {
                video.srcObject.getTracks().forEach(track => track.stop());
            }
            
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('fps').textContent = '0';
        }

        function takeScreenshot() {
            const link = document.createElement('a');
            link.download = `pose-${Date.now()}.jpg`;
            link.href = resultImage.style.display === 'block' ? resultImage.src : canvas.toDataURL();
            link.click();
        }
        
        function showGPUInfo() {
            fetch('/gpu_info')
                .then(r => r.json())
                .then(data => {
                    if (data.available === false) {
                        alert('GPU 不可用');
                        return;
                    }
                    
                    const info = `
GPU 详细信息：

设备名称: ${data.device_name}
CUDA 版本: ${data.cuda_version}
PyTorch 版本: ${data.torch_version}

显存信息:
  总显存: ${data.total_memory_gb} GB
  已分配: ${data.memory_allocated_gb} GB
  已预留: ${data.memory_reserved_gb} GB
  峰值分配: ${data.max_memory_allocated_gb} GB
                    `.trim();
                    
                    alert(info);
                })
                .catch(err => alert('获取 GPU 信息失败: ' + err.message));
        }

        document.getElementById('startBtn').addEventListener('click', startDetection);
        document.getElementById('stopBtn').addEventListener('click', stopDetection);
        document.getElementById('screenshotBtn').addEventListener('click', takeScreenshot);
    </script>
</body>
</html>
'''

def main():
    """启动服务"""
    print("=" * 60)
    print("MMPose 实时姿态估计后端服务 (GPU 优化)")
    print("=" * 60)
    
    # 初始化模型
    init_models()
    
    if not model_loaded:
        print("\n警告：模型加载失败，服务可能无法正常工作")
        print("请检查依赖安装：")
        print("  pip install torch torchvision")
        print("  pip install -U openmim")
        print("  mim install mmengine mmcv mmdet mmpose")
        print("或安装 MediaPipe: pip install mediapipe")
        return
    
    # 启动服务
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🚀 服务已启动: http://localhost:{port}")
    print(f"📊 健康检查: http://localhost:{port}/health")
    print(f"🎮 GPU 信息: http://localhost:{port}/gpu_info")
    print(f"🎨 演示页面: http://localhost:{port}")
    print(f"\n按 Ctrl+C 停止服务\n")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )

if __name__ == '__main__':
    main()
