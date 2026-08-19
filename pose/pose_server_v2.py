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

from flask import Flask, request, jsonify, render_template_string, send_file
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
from threading import Lock, Thread
import uuid
import tempfile
import subprocess
import shutil

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
infer_lock = Lock()

JOB_DIR = os.environ.get('POSE_JOB_DIR', os.path.join(tempfile.gettempdir(), 'tenclip_pose_jobs'))
video_jobs = {}
video_jobs_lock = Lock()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_VIDEO_FRAMES = 48
TARGET_VIDEO_FPS = 6

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
    """初始化 MMPose RTMPose 模型。MMPose 1.3.2 Inferencer 不认 rtmpose-m 这种简称。"""
    global pose_model, detector_model, model_loaded, model_config
    
    check_gpu()
    
    # 人体默认 alias 是 human（RTMPose-m + RTMDet-m）
    model_name_map = {
        's': 'rtmpose-s_8xb256-420e_coco-256x192',
        'm': 'human',
        'l': 'rtmpose-l_8xb256-420e_coco-256x192',
    }
    
    try:
        from mmpose.apis import MMPoseInferencer
        import torch

        nthreads = int(os.environ.get('OMP_NUM_THREADS', '4'))
        torch.set_num_threads(max(1, nthreads))
        
        if model_size not in model_name_map and not gpu_available:
            model_size = 's'
        model_name = model_name_map.get(model_size, 'human')
        device = 'cuda:0' if gpu_available else 'cpu'
        
        print(f"\n加载 RTMPose {model_name} 到 {device}...")
        
        try:
            pose_model = MMPoseInferencer(
                pose2d=model_name,
                pose2d_weights=None,
                device=device
            )
        except Exception as first_err:
            if model_name != 'human':
                print(f"⚠ {model_name} 不可用 ({first_err})，改用 human")
                model_name = 'human'
                pose_model = MMPoseInferencer(
                    pose2d=model_name,
                    pose2d_weights=None,
                    device=device
                )
            else:
                raise
        
        model_loaded = True
        model_config = {
            'model_name': model_name,
            'device': device,
            'model_size': model_size,
            'backend': 'MMPose',
        }
        
        print(f"✓ {model_name} 加载成功")
        
        if gpu_available:
            print("预热 GPU...")
            dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
            _ = next(pose_model(dummy_img, return_vis=False))
            print("✓ GPU 预热完成")
        else:
            print("⚠ CPU 模式: 预期较慢，建议 --size s")
        
    except Exception as e:
        print(f"✗ MMPose 加载失败: {e}")
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
    """编码图像为 base64（CPU 实时用较低 JPEG 质量，减小回传）"""
    _, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
    return base64.b64encode(buffer).decode('utf-8')


_COCO_EDGES = (
    (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
)


def _downscale(image, max_side=320):
    h, w = image.shape[:2]
    m = max(h, w)
    if m <= max_side:
        return image
    scale = max_side / float(m)
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def _draw_pose(image, predictions, confidence_threshold=0.5):
    vis = image.copy()
    color = (0, 140, 255)
    for pred in predictions:
        kpts = pred.get('keypoints') or []
        scores = pred.get('keypoint_scores')
        if scores is None:
            scores = [1.0] * len(kpts)
        pts = []
        for kpt, score in zip(kpts, scores):
            x, y = int(kpt[0]), int(kpt[1])
            sc = float(score)
            pts.append((x, y, sc))
            if sc >= confidence_threshold:
                cv2.circle(vis, (x, y), 3, color, -1, lineType=cv2.LINE_AA)
        for a, b in _COCO_EDGES:
            if a < len(pts) and b < len(pts) and pts[a][2] >= confidence_threshold and pts[b][2] >= confidence_threshold:
                cv2.line(vis, (pts[a][0], pts[a][1]), (pts[b][0], pts[b][1]), color, 2, lineType=cv2.LINE_AA)
    return vis

# ============ 姿态检测 ============

def detect_pose(image, return_visualization=True, confidence_threshold=0.5, encode_image=True):
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
        # CPU 上缩小输入、关闭 MMPose 自带可视化（改用轻量 OpenCV 画骨架）
        infer_img = _downscale(image, int(os.environ.get('POSE_MAX_SIDE', '320')))
        with infer_lock:
            results = next(pose_model(infer_img, return_vis=False))
        
        all_keypoints = []
        num_people = 0
        predictions = results.get('predictions', []) if isinstance(results, dict) else []
        if predictions and isinstance(predictions[0], list):
            predictions = predictions[0]
        
        if predictions:
            num_people = len(predictions)
            
            for person_idx, pred in enumerate(predictions):
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
        
        vis_image = infer_img
        if return_visualization:
            vis_image = _draw_pose(infer_img, predictions, confidence_threshold)
        
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
            'keypoints': all_keypoints[0]['keypoints'] if all_keypoints else [],
            'image': encode_image_to_base64(vis_image) if (return_visualization and encode_image) else None,
            'vis_bgr': vis_image if (return_visualization and not encode_image) else None,
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


def _job_update(task_id, **kwargs):
    with video_jobs_lock:
        job = video_jobs.get(task_id)
        if not job:
            return
        job.update(kwargs)


def _transcode_h264(src, dst):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return False
    cmd = [
        ffmpeg, '-y', '-i', src,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an',
        '-movflags', '+faststart', dst,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return os.path.isfile(dst) and os.path.getsize(dst) > 0
    except Exception:
        return False


def _run_video_job(task_id, src_path):
    _job_update(task_id, status='running', message='正在抽帧', progress=0.02)
    cap = cv2.VideoCapture(src_path)
    if not cap.isOpened():
        _job_update(task_id, status='failed', error='无法打开视频')
        return
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(src_fps / TARGET_VIDEO_FPS)))
    frames = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            frames.append(frame)
            if len(frames) >= MAX_VIDEO_FRAMES:
                break
        idx += 1
    cap.release()
    if not frames:
        _job_update(task_id, status='failed', error='视频没有可读帧')
        return

    vis_frames = []
    total = len(frames)
    for i, frame in enumerate(frames):
        result = detect_pose(frame, return_visualization=True, encode_image=False)
        if not result.get('success'):
            vis_frames.append(_downscale(frame))
        else:
            vis_frames.append(result.get('vis_bgr') or _downscale(frame))
        _job_update(
            task_id,
            progress=0.05 + 0.85 * ((i + 1) / total),
            message='分析中 %s/%s' % (i + 1, total),
            frame_count=total,
        )

    h, w = vis_frames[0].shape[:2]
    raw_mp4 = os.path.join(JOB_DIR, task_id + '_raw.mp4')
    out_mp4 = os.path.join(JOB_DIR, task_id + '.mp4')
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(raw_mp4, fourcc, float(TARGET_VIDEO_FPS), (w, h))
    for vis in vis_frames:
        if vis.shape[1] != w or vis.shape[0] != h:
            vis = cv2.resize(vis, (w, h))
        writer.write(vis)
    writer.release()

    if _transcode_h264(raw_mp4, out_mp4):
        try:
            os.remove(raw_mp4)
        except OSError:
            pass
        result_path = out_mp4
    else:
        result_path = raw_mp4

    _job_update(
        task_id,
        status='succeeded',
        progress=1.0,
        message='完成',
        result_path=result_path,
        frame_count=total,
    )


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

@app.route('/detect', methods=['POST'])
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

@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'model_loaded': model_loaded,
        'model_config': model_config,
        'gpu_info': gpu_info,
    })

@app.route('/gpu_info', methods=['GET'])
def gpu_info_route():
    return jsonify(gpu_info)


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

@app.route('/analyze-video', methods=['POST'])
def analyze_video():
    if not model_loaded:
        return jsonify({'error': '模型未加载'}), 503
    f = request.files.get('video')
    if f is None or not f.filename:
        return jsonify({'error': '缺少 video 文件'}), 400
    os.makedirs(JOB_DIR, exist_ok=True)
    task_id = uuid.uuid4().hex[:16]
    ext = os.path.splitext(f.filename)[1].lower() or '.mp4'
    if ext not in ('.mp4', '.mov', '.avi', '.m4v'):
        ext = '.mp4'
    src_path = os.path.join(JOB_DIR, task_id + '_src' + ext)
    f.save(src_path)
    if os.path.getsize(src_path) > MAX_UPLOAD_BYTES:
        try:
            os.remove(src_path)
        except OSError:
            pass
        return jsonify({'error': '视频超过 20MB'}), 400
    with video_jobs_lock:
        video_jobs[task_id] = {
            'task_id': task_id,
            'status': 'queued',
            'progress': 0.0,
            'message': '排队中',
            'frame_count': 0,
            'error': None,
            'result_path': None,
        }
    Thread(target=_run_video_job, args=(task_id, src_path), daemon=True).start()
    return jsonify({'task_id': task_id}), 202


@app.route('/analyze-video/status', methods=['GET'])
def analyze_video_status():
    task_id = (request.args.get('id') or '').strip()
    with video_jobs_lock:
        job = video_jobs.get(task_id)
        if not job:
            return jsonify({'error': '任务不存在'}), 404
        return jsonify({
            'task_id': job['task_id'],
            'status': job['status'],
            'progress': round(float(job.get('progress') or 0), 3),
            'message': job.get('message') or '',
            'frame_count': job.get('frame_count') or 0,
            'error': job.get('error'),
        })


@app.route('/analyze-video/file', methods=['GET'])
def analyze_video_file():
    task_id = (request.args.get('id') or '').strip()
    with video_jobs_lock:
        job = video_jobs.get(task_id)
        if not job:
            return jsonify({'error': '任务不存在'}), 404
        if job.get('status') != 'succeeded' or not job.get('result_path'):
            return jsonify({'error': '结果未就绪'}), 409
        path = job['result_path']
    if not os.path.isfile(path):
        return jsonify({'error': '结果文件丢失'}), 404
    return send_file(path, mimetype='video/mp4', as_attachment=False, download_name='pose.mp4')


# ============ 启动 ============

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='RTMpose v2 后端')
    parser.add_argument('--size', choices=['s', 'm', 'l'], default='s',
                        help='模型大小，CPU 建议 s')
    parser.add_argument('--port', type=int, default=int(os.environ.get('POSE_PORT', '5000')))
    args = parser.parse_args()

    print("=" * 60)
    print("RTMpose 实时姿态估计后端 v2")
    print("=" * 60)
    
    try:
        init_models(model_size=args.size)
    except Exception as e:
        print(f"模型初始化失败: {e}")
        sys.exit(1)
    
    print("\n启动 Flask 服务...")
    print(f"访问地址: http://0.0.0.0:{args.port}")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)
