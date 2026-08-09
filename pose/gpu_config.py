"""
MMPose GPU 优化配置
针对 NVIDIA RTX 3060 (12GB VRAM)
"""

# GPU 优化参数
GPU_CONFIG = {
    # 设备配置
    'device': 'cuda:0',  # 使用第一块 GPU
    
    # RTMPose 模型选择（针对 3060 优化）
    # 3060 有 12GB 显存，可以跑较大的模型
    'model': 'rtmpose-l',  # large 模型，最佳精度
    # 'model': 'rtmpose-m',  # medium 模型，平衡
    # 'model': 'rtmpose-s',  # small 模型，最快
    
    # 输入分辨率
    'input_size': (256, 192),  # 标准分辨率
    # 'input_size': (384, 288),  # 高分辨率，更精确但更慢
    
    # 批处理大小
    'batch_size': 1,  # 实时检测建议为 1
    
    # 性能优化
    'enable_amp': False,  # 混合精度（3060 支持，但实时检测通常不需要）
    'cudnn_benchmark': True,  # 自动优化卷积算法
    'num_threads': 4,  # DataLoader 线程数
    
    # 显存优化
    'max_memory_allocated': 8 * 1024**3,  # 最大使用 8GB 显存（留 4GB 给系统）
    'empty_cache_freq': 100,  # 每 100 帧清空一次缓存
    
    # 检测器配置（用于多人场景）
    'detector': 'rtmdet-m',  # RTMDet medium
    'det_score_thr': 0.5,  # 检测置信度阈值
}

# 性能预期（基于 RTX 3060）
PERFORMANCE_TARGETS = {
    'rtmpose-t': {'fps': 200, 'latency_ms': 5},
    'rtmpose-s': {'fps': 150, 'latency_ms': 7},
    'rtmpose-m': {'fps': 100, 'latency_ms': 10},
    'rtmpose-l': {'fps': 80, 'latency_ms': 12},
}

# 根据显存动态调整
def get_optimal_config(available_memory_gb):
    """根据可用显存返回最佳配置"""
    if available_memory_gb >= 10:
        return {
            'model': 'rtmpose-l',
            'input_size': (384, 288),
            'batch_size': 1
        }
    elif available_memory_gb >= 6:
        return {
            'model': 'rtmpose-m',
            'input_size': (256, 192),
            'batch_size': 1
        }
    else:
        return {
            'model': 'rtmpose-s',
            'input_size': (256, 192),
            'batch_size': 1
        }

# CUDA 优化配置
CUDA_ENV = {
    'CUDA_VISIBLE_DEVICES': '0',
    'PYTORCH_CUDA_ALLOC_CONF': 'max_split_size_mb:512',
    'CUDNN_BENCHMARK': '1',
}
