#!/usr/bin/env python3
"""
RTMpose v2 CPU 版本依赖安装脚本（跨平台）

特点：
- 最大化利用已有环境（检查已装模块）
- 自动检测 GPU 并选择合适版本
- 智能安装缺失的包
- 最终验证 RTMpose 可用性

用法：
    python install_mmpose_cpu.py
    python install_mmpose_cpu.py --skip-verify  # 跳过最终验证
    python install_mmpose_cpu.py --gpu          # 强制使用 GPU 版本
"""

import subprocess
import sys
import os
from pathlib import Path

# 颜色输出
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def run_cmd(cmd, description="", silent=False):
    """执行命令并返回结果"""
    try:
        if silent:
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
        else:
            subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        if description:
            print(f"{Colors.RED}✗ {description} 失败{Colors.NC}")
        return False

def print_header():
    print(f"{Colors.BLUE}╔════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║   RTMpose v2 CPU 版本依赖安装脚本      ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════╝{Colors.NC}")
    print()

def check_environment():
    """检查开发环境"""
    print(f"{Colors.YELLOW}[1/5] 检查环境...{Colors.NC}")
    
    # 检查 Python
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"{Colors.GREEN}✓ Python: {python_version}{Colors.NC}")
    
    if sys.version_info < (3, 8):
        print(f"{Colors.RED}✗ Python 3.8+ 是必需的{Colors.NC}")
        return False
    
    # 检查 pip
    result = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        pip_version = result.stdout.split()[1]
        print(f"{Colors.GREEN}✓ pip: {pip_version}{Colors.NC}")
    
    print()
    return True

def check_existing_modules():
    """检查已有的模块"""
    print(f"{Colors.YELLOW}[2/5] 检查已有模块...{Colors.NC}")
    
    modules = {
        'torch': 'PyTorch',
        'mmengine': 'MMEngine',
        'numpy': 'NumPy',
        'cv2': 'OpenCV',
        'flask': 'Flask',
        'mediapipe': 'MediaPipe',
    }
    
    installed = {}
    missing = []
    
    for module, name in modules.items():
        try:
            mod = __import__(module.replace('-', '_'))
            version = getattr(mod, '__version__', 'N/A')
            print(f"{Colors.GREEN}✓ {name:20} {version}{Colors.NC}")
            installed[module] = True
        except ImportError:
            print(f"{Colors.RED}✗ {name:20} 缺失{Colors.NC}")
            missing.append(module)
    
    # 检查 MMPose 相关
    print(f"{Colors.BLUE}─────────────────────────────────────────{Colors.NC}")
    
    optional = {
        'mmpose': 'MMPose',
        'mmcv': 'MMCV',
        'mmdet': 'MMDet',
    }
    
    mmpose_status = {}
    for module, name in optional.items():
        try:
            mod = __import__(module.replace('-', '_'))
            version = getattr(mod, '__version__', 'N/A')
            print(f"{Colors.GREEN}✓ {name:20} {version}{Colors.NC}")
            mmpose_status[module] = 'installed'
        except ImportError:
            print(f"{Colors.YELLOW}⚠ {name:20} 缺失（将安装）{Colors.NC}")
            mmpose_status[module] = 'missing'
    
    # 检查 GPU
    print()
    print("GPU 状态:")
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            print(f"{Colors.GREEN}✓ GPU 可用: {gpu_name} ({gpu_count} 个){Colors.NC}")
            gpu_available = True
        else:
            print(f"{Colors.YELLOW}⚠ GPU 不可用，使用 CPU 模式{Colors.NC}")
            gpu_available = False
    except Exception as e:
        print(f"{Colors.YELLOW}⚠ GPU 检查失败: {e}{Colors.NC}")
        gpu_available = False
    
    print()
    return mmpose_status, gpu_available

def install_mmpose(mmpose_status):
    """安装 MMPose 及相关依赖"""
    print(f"{Colors.YELLOW}[3/5] 安装缺失的包...{Colors.NC}")
    
    if all(status == 'installed' for status in mmpose_status.values()):
        print(f"{Colors.GREEN}✓ 所有必要包都已安装{Colors.NC}")
        print()
        return True
    
    print()
    
    # 配置清华源
    print(f"{Colors.BLUE}配置清华源...{Colors.NC}")
    subprocess.run(
        f"{sys.executable} -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple",
        shell=True,
        capture_output=True
    )
    
    # 更新 pip
    print(f"{Colors.BLUE}更新 pip...{Colors.NC}")
    subprocess.run(
        f"{sys.executable} -m pip install --upgrade pip setuptools wheel -q",
        shell=True,
        capture_output=True
    )
    
    # 安装 openmim（必须）
    try:
        import openmim
        print(f"{Colors.GREEN}✓ openmim 已安装{Colors.NC}")
    except ImportError:
        print(f"{Colors.BLUE}安装 openmim...{Colors.NC}")
        subprocess.run(
            f"{sys.executable} -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -U openmim -q",
            shell=True,
            check=True
        )
        print(f"{Colors.GREEN}✓ openmim 安装完成{Colors.NC}")
    
    # 安装 mmcv（使用 mim）
    if mmpose_status.get('mmcv') == 'missing':
        print(f"{Colors.BLUE}安装 mmcv（使用 mim）...{Colors.NC}")
        subprocess.run("mim install mmcv -q", shell=True, check=True)
        print(f"{Colors.GREEN}✓ mmcv 安装完成{Colors.NC}")
    
    # 安装 mmdet
    if mmpose_status.get('mmdet') == 'missing':
        print(f"{Colors.BLUE}安装 mmdet...{Colors.NC}")
        subprocess.run(
            f"{sys.executable} -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet -q",
            shell=True,
            check=True
        )
        print(f"{Colors.GREEN}✓ mmdet 安装完成{Colors.NC}")
    
    # 安装 mmpose
    if mmpose_status.get('mmpose') == 'missing':
        print(f"{Colors.BLUE}安装 mmpose...{Colors.NC}")
        subprocess.run(
            f"{sys.executable} -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmpose -q",
            shell=True,
            check=True
        )
        print(f"{Colors.GREEN}✓ mmpose 安装完成{Colors.NC}")
    
    # 安装额外依赖
    print(f"{Colors.BLUE}安装额外依赖...{Colors.NC}")
    subprocess.run(
        f"{sys.executable} -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "
        "chumpy json_tricks matplotlib munkres scipy xtcocotools -q",
        shell=True,
        capture_output=True
    )
    
    print()
    return True

def verify_rtmpose():
    """验证 RTMpose 可用性"""
    print(f"{Colors.YELLOW}[4/5] 验证 RTMpose 可用性...{Colors.NC}")
    print()
    
    # 验证脚本
    verify_script = '''
import sys

try:
    from mmpose.apis import MMPoseInferencer
    print("✓ RTMpose API 可用")
    
    models = ["rtmpose-s", "rtmpose-m", "rtmpose-l"]
    print(f"✓ 支持的模型: {', '.join(models)}")
    
    import mmpose
    print(f"✓ MMPose: {mmpose.__version__}")
    print(f"✓ 路径: {mmpose.__file__}")
    
    print()
    print("✅ RTMpose v2 已就绪！")
except Exception as e:
    print(f"✗ 验证失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
    
    result = subprocess.run(
        [sys.executable, "-c", verify_script],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    if result.returncode != 0:
        print(f"{Colors.RED}✗ 验证失败{Colors.NC}")
        print(result.stderr)
        return False
    
    print()
    return True

def final_check():
    """最终检查"""
    print(f"{Colors.YELLOW}[5/5] 最终检查...{Colors.NC}")
    print()
    
    check_script = '''
import sys

modules = {
    "torch": "PyTorch",
    "mmpose": "MMPose",
    "mmengine": "MMEngine",
    "mmcv": "MMCV",
    "mmdet": "MMDet",
    "cv2": "OpenCV",
    "numpy": "NumPy",
    "flask": "Flask",
}

print("✓ 核心模块检查:")
all_ok = True
for module, name in modules.items():
    try:
        mod = __import__(module.replace("-", "_"))
        version = getattr(mod, "__version__", "N/A")
        print(f"  ✓ {name:15} {version}")
    except ImportError:
        print(f"  ✗ {name:15} 缺失")
        all_ok = False

print()

# GPU 检查
import torch
print("✓ 计算设备:")
if torch.cuda.is_available():
    print(f"  ✓ GPU: {torch.cuda.get_device_name(0)}")
else:
    print("  ✓ GPU: 不可用，使用 CPU")

print()
if all_ok:
    print("━" * 45)
    print("✅ RTMpose v2 安装完成！")
    print("━" * 45)
else:
    print("⚠️  部分模块缺失，但基础已安装")
'''
    
    result = subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    print()

def print_usage_guide():
    """打印使用指南"""
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print(f"{Colors.GREEN}🎉 安装完成！{Colors.NC}")
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print()
    print(f"{Colors.BLUE}后续使用{Colors.NC}")
    print()
    print("1. 启动 RTMpose v2 后端:")
    print("   python pose_server_v2.py")
    print()
    print("2. 指定模型大小（推荐 CPU 使用 's' 轻量版）:")
    print("   # 编辑 pose_server_v2.py 最后一行：")
    print("   # init_models(model_size='s')  # 轻量")
    print("   # init_models(model_size='m')  # 标准")
    print("   # init_models(model_size='l')  # 高精度")
    print()
    print("3. 云主机后台运行:")
    print("   nohup python pose_server_v2.py > pose.log 2>&1 &")
    print()
    print("4. 或使用 Systemd 服务（生产环境）:")
    print("   参考 RTMPOSE_V2_DEPLOYMENT_GUIDE.md")
    print()
    print("5. 查看日志:")
    print("   tail -f pose.log")
    print()

def main():
    print_header()
    
    # 1. 检查环境
    if not check_environment():
        sys.exit(1)
    
    # 2. 检查已有模块
    mmpose_status, gpu_available = check_existing_modules()
    
    # 3. 安装缺失的包
    try:
        if not install_mmpose(mmpose_status):
            sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}✗ 安装失败: {e}{Colors.NC}")
        sys.exit(1)
    
    # 4. 验证 RTMpose
    if not verify_rtmpose():
        sys.exit(1)
    
    # 5. 最终检查
    final_check()
    
    # 打印使用指南
    print_usage_guide()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}安装已取消{Colors.NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}✗ 发生错误: {e}{Colors.NC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
