#!/usr/bin/env python3
"""
RTMpose v2 快速启动脚本（跨平台）

用法:
    python start_rtmpose_v2.py              # 默认使用 m (标准)
    python start_rtmpose_v2.py --size s    # 使用 s (轻量)
    python start_rtmpose_v2.py --size l    # 使用 l (高精度)
    python start_rtmpose_v2.py --help      # 显示帮助
"""

import sys
import argparse
import subprocess
from pathlib import Path

# 颜色输出
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_header():
    print(f"{Colors.BLUE}╔════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║    RTMpose v2 实时姿态检测服务        ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════╝{Colors.NC}")
    print()

def check_dependencies():
    """检查必要的 Python 依赖"""
    print(f"{Colors.YELLOW}[1/4] 检查依赖...{Colors.NC}")
    
    required_modules = {
        'flask': 'Flask',
        'torch': 'PyTorch',
        'mmpose': 'MMPose',
        'cv2': 'OpenCV',
        'numpy': 'NumPy',
    }
    
    missing = []
    for module, name in required_modules.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(f"{name} ({module})")
    
    if missing:
        print(f"{Colors.RED}✗ 缺少依赖: {', '.join(missing)}{Colors.NC}")
        print()
        print("请运行以下命令安装:")
        print()
        print("  # 基础依赖")
        print("  pip install flask flask-cors opencv-python numpy pillow")
        print()
        print("  # PyTorch (GPU 版本)")
        print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
        print()
        print("  # PyTorch (CPU 版本)")
        print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu")
        print()
        print("  # MMPose")
        print("  pip install -U openmim")
        print("  mim install mmengine mmcv mmdet mmpose")
        print()
        return False
    
    print(f"{Colors.GREEN}✓ 所有依赖已就绪{Colors.NC}")
    
    # 检查 GPU
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"{Colors.GREEN}✓ GPU 可用: {gpu_name}{Colors.NC}")
        else:
            print(f"{Colors.YELLOW}⚠ GPU 不可用，将使用 CPU（性能较慢）{Colors.NC}")
    except Exception as e:
        print(f"{Colors.YELLOW}⚠ GPU 检查失败: {e}{Colors.NC}")
    
    print()
    return True

def show_model_info(model_size):
    """显示模型信息"""
    print(f"{Colors.YELLOW}[3/4] 模型配置...{Colors.NC}")
    
    model_info = {
        's': {
            'name': 'rtmpose-s (轻量)',
            'inference': '8-15 ms',
            'fps': '60-100',
            'vram': '1.5 GB',
        },
        'm': {
            'name': 'rtmpose-m (标准，推荐)',
            'inference': '15-25 ms',
            'fps': '40-65',
            'vram': '3-4 GB',
        },
        'l': {
            'name': 'rtmpose-l (高精度)',
            'inference': '30-50 ms',
            'fps': '20-33',
            'vram': '8-10 GB',
        },
    }
    
    info = model_info.get(model_size, model_info['m'])
    print(f"{Colors.GREEN}模型: {info['name']}{Colors.NC}")
    print(f"  推理时间: {info['inference']}")
    print(f"  FPS: {info['fps']}")
    print(f"  显存: {info['vram']}")
    print()

def start_server(model_size):
    """启动 RTMpose v2 服务器"""
    print(f"{Colors.YELLOW}[4/4] 启动服务...{Colors.NC}")
    print(f"{Colors.GREEN}✓ 启动 RTMpose v2 后端{Colors.NC}")
    print()
    
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print("Web UI: http://localhost:5000")
    print("API:    http://localhost:5000/api/detect")
    print("Health: http://localhost:5000/api/health")
    print()
    print("按 Ctrl+C 停止服务")
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print()
    
    # 启动服务
    try:
        # 动态导入并启动
        from pose_server_v2 import app, init_models
        
        print(f"初始化模型 (size={model_size})...")
        init_models(model_size=model_size)
        
        print("\n🚀 服务已启动！\n")
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True,
            use_reloader=False,  # 防止双重启动
        )
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⏹ 服务已停止{Colors.NC}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}✗ 启动失败: {e}{Colors.NC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='RTMpose v2 快速启动脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python start_rtmpose_v2.py              # 默认使用 m (标准)
  python start_rtmpose_v2.py --size s    # 使用 s (轻量)
  python start_rtmpose_v2.py --size l    # 使用 l (高精度)
        '''
    )
    
    parser.add_argument(
        '--size', '-s',
        choices=['s', 'm', 'l'],
        default='m',
        help='模型大小: s(轻量) m(标准) l(高精度)'
    )
    
    args = parser.parse_args()
    
    # 设置当前目录为脚本所在目录
    script_dir = Path(__file__).parent
    import os
    os.chdir(script_dir)
    
    # 打印头部
    print_header()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 显示模型信息
    show_model_info(args.size)
    
    # 启动服务
    start_server(args.size)

if __name__ == '__main__':
    main()
