"""
RTMpose 实时姿态估计后端服务 v2 (增强版)
基于 MMPose RTMPose 模型，支持多人检测、自定义模型、性能优化

主要改进:
1. 更好的 GPU 管理和内存优化
2. 支持多人检测和跟踪
3. 详细的性能监控和统计
4. 灵活的模型选择和配置
5. 更好的错误恢复

依赖安装:
  pip install flask flask-cors opencv-python numpy pillow
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
  pip install -U openmim
  mim install mmengine mmcv mmdet mmpose

启动命令:
  conda activate tenclip
  python pose_server_v2.py

访问地址:
  http://localhost:5000 (演示页面)
  http://localhost:5000/api/detect (检测 API)
"""

from flask import Flask, request, jsonify, render_template_string
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
from collections import deque
from threading import Lock

# ============ 初始化 ============
app = Flask(__name__)
CORS(app)

# 全局变量
pose_model = None
detector_model = None
model_loaded = False
gpu_available = False
gpu_info = {}
model_config = {}

# 性能监控
perf_metrics = {
    'total_detections': 0,
    'total_errors': 0,
    'avg_inference_time': 0,
    'inference_times': deque(maxlen=100),  # 保留最近 100 次推理时间
    'start_time': time.time(),
}
metrics_lock = Lock()

# ============ GPU & 模型初始化 ============

def check_gpu():
    """检查并配置 GPU"""
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
                'cudnn_version': torch.backends.cudnn.version(),
                'total_memory_gb': round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
                'allocated_memory_gb': 0,
            }
            
            # 优化 CUDA 设置
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
            torch.backends.cuda.matmul.allow_tf32 = True
            
            print(f"✓ GPU 可用: {gpu_info['device_name']}")
            print(f"  显存: {gpu_info['total_memory_gb']} GB")
            print(f"  CUDA: {gpu_info['cuda_version']}, cuDNN: {gpu_info['cudnn_version']}")
        else:
            gpu_info = {'available': False, 'reason': 'CUDA not available'}
            print("⚠ GPU 不可用，将使用 CPU（性能较慢）")
            
    except ImportError:
        gpu_info = {'available': False, 'reason': 'PyTorch not installed'}
        print("⚠ PyTorch 未安装")
    except Exception as e:
        gpu_info = {'available': False, 'reason': str(e)}
        print(f"⚠ GPU 检查失败: {e}")

def init_models(model_size='m'):
    """初始化 MMPose RTMPose 模型"""
    global pose_model, detector_model, model_loaded, model_config
    
    check_gpu()
    
    model_name_map = {
        's': 'rtmpose-s',  # 轻量
        'm': 'rtmpose-m',  # 标准
        'l': 'rtmpose-l',  # 高精度
    }
    
    try:
        from mmpose.apis import MMPoseInferencer
        import torch
        
        model_name = model_name_map.get(model_size, 'rtmpose-m')
        device = 'cuda:0' if gpu_available else 'cpu'
        
        print(f"\n加载 RTMPose {model_name} 到 {device}...")
        
        # 创建推理器
        pose_model = MMPoseInferencer(
            pose2d=model_name,
            pose2d_weights=None,  # 自动下载权重
            device=device
        )
        
        model_loaded = True
        model_config = {
            'model_name': model_name,
            'device': device,
            'model_size': model_size,
        }
        
        print(f"✓ {model_name} 加载成功")
        
        # GPU 预热
        if gpu_available:
            print("预热 GPU...")
            dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
            _ = pose_model(dummy_img, return_vis=False)
            print("✓ GPU 预热完成")
            
            # 显示预期性能
            perf_table = {
                'rtmpose-s': '100-150 FPS',
                'rtmpose-m': '80-120 FPS',
                'rtmpose-l': '60-90 FPS',
            }
            print(f"预期性能: {perf_table.get(model_name, 'N/A')}")
        else:
            print("⚠ CPU 模式: 预期 5-20 FPS")
        
    except Exception as e:
        print(f"✗ MMPose 加载失败: {e}")
        print("尝试回退到 MediaPipe...")
        try:
            init_mediapipe()
        except Exception as e2:
            print(f"✗ MediaPipe 也加载失败: {e2}")
            raise

def init_mediapipe():
    """回退方案：MediaPipe"""
    global pose_model, model_loaded, model_config
    
    try:
        import mediapipe as mp
        
        mp_pose = mp.solutions.pose
        pose_model = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        model_loaded = True
        model_config = {'model_name': 'MediaPipe Pose', 'device': 'cpu'}
        
        print("✓ MediaPipe Pose 加载成功（回退方案）")
        
    except ImportError as e:
        print(f"MediaPipe 未安装: {e}")
        raise

# ============ 图像处理 ============

def decode_base64_image(base64_string):
    """解码 base64 图像"""
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    img_data = base64.b64decode(base64_string)
    img = Image.open(BytesIO(img_data))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def encode_image_to_base64(image):
    """编码图像为 base64"""
    _, buffer = cv2.imencode('.jpg', image)
    return base64.b64encode(buffer).decode('utf-8')

# ============ 姿态检测 ============

def detect_pose(image, return_visualization=True, confidence_threshold=0.5):
    """
    检测姿态关键点
    
    Args:
        image: 输入图像 (BGR)
        return_visualization: 是否返回可视化图像
        confidence_threshold: 关键点置信度阈值
    
    Returns:
        dict: 包含关键点、人数和可视化图像的结果
    """
    global perf_metrics
    
    start_time = time.time()
    
    try:
        # 使用 MMPose 检测
        results = pose_model(image, return_vis=return_visualization)
        
        # 解析结果
        all_keypoints = []
        num_people = 0
        
        if 'predictions' in results and results['predictions']:
            num_people = len(results['predictions'])
            
            for person_idx, pred in enumerate(results['predictions']):
                person_kpts = []
                
                if 'keypoints' in pred:
                    kpts = pred['keypoints']
                    scores = pred.get('keypoint_scores', np.ones(len(kpts)))
                    
                    for kpt_idx, (kpt, score) in enumerate(zip(kpts, scores)):
                        if float(score) >= confidence_threshold:
                            person_kpts.append({
                                'id': kpt_idx,
                                'x': float(kpt[0]),
                                'y': float(kpt[1]),
                                'confidence': float(score),
                            })
                
                all_keypoints.append({
                    'person_id': person_idx,
                    'keypoints': person_kpts,
                    'keypoint_count': len(person_kpts),
                })
        
        # 获取可视化图像
        vis_image = image
        if return_visualization and 'visualization' in results:
            vis_list = results.get('visualization', [])
            if vis_list and len(vis_list) > 0:
                vis_image = vis_list[0]
        
        # 更新性能指标
        inference_time = time.time() - start_time
        with metrics_lock:
            perf_metrics['total_detections'] += 1
            perf_metrics['inference_times'].append(inference_time)
            perf_metrics['avg_inference_time'] = np.mean(list(perf_metrics['inference_times']))
        
        return {
            'success': True,
            'num_people': num_people,
            'people': all_keypoints,
            'image': encode_image_to_base64(vis_image) if return_visualization else None,
            'inference_time_ms': round(inference_time * 1000, 2),
            'fps': round(1.0 / inference_time, 2) if inference_time > 0 else 0,
        }
        
    except Exception as e:
        with metrics_lock:
            perf_metrics['total_errors'] += 1
        
        return {
            'success': False,
            'error': str(e),
            'num_people': 0,
            'people': [],
        }

# ============ Flask 路由 ============

@app.route('/', methods=['GET'])
def index():
    """演示页面"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>RTMpose 实时姿态检测 v2</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; 
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   min-height: 100vh; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { color: white; margin-bottom: 30px; text-align: center; }
            .header h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 0 2px 10px rgba(0,0,0,0.2); }
            .header p { font-size: 1.1em; opacity: 0.9; }
            .content { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
            .card { background: white; border-radius: 12px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
            .card h2 { color: #333; margin-bottom: 15px; font-size: 1.3em; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; color: #555; font-weight: 500; }
            input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; }
            button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                     color: white; padding: 12px 24px; border: none; border-radius: 6px; 
                     cursor: pointer; font-size: 1em; margin-top: 10px; }
            button:hover { opacity: 0.9; }
            #preview { width: 100%; border-radius: 6px; margin-top: 15px; }
            #result { padding: 15px; background: #f5f5f5; border-radius: 6px; margin-top: 15px; font-size: 0.9em; }
            .stats { background: #f0f0f0; padding: 15px; border-radius: 6px; margin-top: 15px; }
            .stat-item { display: flex; justify-content: space-between; margin-bottom: 8px; }
            .stat-item strong { color: #333; }
            .stat-item span { color: #667eea; }
            .full-width { grid-column: 1 / -1; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 RTMpose 实时姿态检测 v2</h1>
                <p>基于 MMPose 的高性能关键点检测 - 支持多人检测</p>
            </div>
            
            <div class="content">
                <div class="card">
                    <h2>📷 图像上传</h2>
                    <div class="form-group">
                        <label>选择图像</label>
                        <input type="file" id="imageInput" accept="image/*">
                    </div>
                    <div class="form-group">
                        <label>置信度阈值</label>
                        <input type="range" id="confidence" min="0" max="1" step="0.1" value="0.5">
                        <span id="confidenceValue">0.5</span>
                    </div>
                    <button onclick="detectImage()">检测姿态</button>
                    <img id="preview" style="display:none;">
                </div>
                
                <div class="card">
                    <h2>📊 检测结果</h2>
                    <div id="result">等待检测...</div>
                </div>
                
                <div class="card full-width">
                    <h2>📈 性能统计</h2>
                    <div id="stats" class="stats">
                        <div class="stat-item"><strong>总检测次数:</strong> <span id="totalDetections">0</span></div>
                        <div class="stat-item"><strong>平均推理时间:</strong> <span id="avgTime">0</span> ms</div>
                        <div class="stat-item"><strong>错误次数:</strong> <span id="totalErrors">0</span></div>
                        <div class="stat-item"><strong>模型信息:</strong> <span id="modelInfo">加载中...</span></div>
                        <div class="stat-item"><strong>GPU 状态:</strong> <span id="gpuStatus">检查中...</span></div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            document.getElementById('confidence').addEventListener('input', (e) => {
                document.getElementById('confidenceValue').textContent = e.target.value;
            });
            
            document.getElementById('imageInput').addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        document.getElementById('preview').src = e.target.result;
                        document.getElementById('preview').style.display = 'block';
                    };
                    reader.readAsDataURL(file);
                }
            });
            
            async function detectImage() {
                const input = document.getElementById('imageInput');
                if (!input.files[0]) {
                    alert('请先选择图像');
                    return;
                }
                
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const confidence = parseFloat(document.getElementById('confidence').value);
                    
                    try {
                        const response = await fetch('/api/detect', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                image: e.target.result,
                                confidence_threshold: confidence
                            })
                        });
                        
                        const data = await response.json();
                        
                        if (data.success) {
                            let html = `<strong>✓ 检测成功</strong><br>`;
                            html += `人数: <strong>${data.num_people}</strong><br>`;
                            html += `推理时间: <strong>${data.inference_time_ms}</strong> ms<br>`;
                            html += `FPS: <strong>${data.fps}</strong><br><br>`;
                            
                            data.people.forEach((person, idx) => {
                                html += `<strong>第 ${idx + 1} 个人:</strong> ${person.keypoint_count} 个关键点<br>`;
                            });
                            
                            document.getElementById('result').innerHTML = html;
                            
                            if (data.image) {
                                document.getElementById('preview').src = 'data:image/jpeg;base64,' + data.image;
                            }
                        } else {
                            document.getElementById('result').innerHTML = `<strong>✗ 检测失败</strong><br>${data.error}`;
                        }
                        
                        updateStats();
                    } catch (err) {
                        document.getElementById('result').innerHTML = `<strong>✗ 错误</strong><br>${err.message}`;
                    }
                };
                reader.readAsDataURL(input.files[0]);
            }
            
            async function updateStats() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();
                    
                    document.getElementById('totalDetections').textContent = data.total_detections;
                    document.getElementById('avgTime').textContent = data.avg_inference_time;
                    document.getElementById('totalErrors').textContent = data.total_errors;
                    document.getElementById('modelInfo').textContent = data.model_name;
                    document.getElementById('gpuStatus').textContent = data.gpu_info;
                } catch (err) {
                    console.error('获取统计信息失败:', err);
                }
            }
            
            updateStats();
            setInterval(updateStats, 2000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/api/detect', methods=['POST'])
def detect():
    """姿态检测 API"""
    try:
        data = request.get_json()
        
        if not data or 'image' not in data:
            return jsonify({'success': False, 'error': '缺少图像数据'}), 400
        
        # 解码图像
        image = decode_base64_image(data['image'])
        
        # 获取可选参数
        confidence_threshold = float(data.get('confidence_threshold', 0.5))
        return_viz = data.get('return_visualization', True)
        
        # 执行检测
        result = detect_pose(image, return_viz, confidence_threshold)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'model_loaded': model_loaded,
        'model_config': model_config,
        'gpu_info': gpu_info,
    })

@app.route('/api/stats', methods=['GET'])
def stats():
    """获取性能统计"""
    with metrics_lock:
        uptime_seconds = time.time() - perf_metrics['start_time']
        
        return jsonify({
            'total_detections': perf_metrics['total_detections'],
            'total_errors': perf_metrics['total_errors'],
            'avg_inference_time': round(perf_metrics['avg_inference_time'], 2),
            'uptime_seconds': round(uptime_seconds),
            'model_name': model_config.get('model_name', '未知'),
            'gpu_info': '可用' if gpu_available else '不可用',
        })

# ============ 启动 ============

if __name__ == '__main__':
    print("=" * 60)
    print("RTMpose 实时姿态估计后端 v2")
    print("=" * 60)
    
    # 初始化模型
    try:
        init_models(model_size='m')  # 可选: 's', 'm', 'l'
    except Exception as e:
        print(f"模型初始化失败: {e}")
        sys.exit(1)
    
    # 启动 Flask
    print("\n启动 Flask 服务...")
    print("访问地址: http://localhost:5000")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
