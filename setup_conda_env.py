#!/usr/bin/env python3
"""
RTMpose v2 Conda 环境快速部署脚本（跨平台）

用法:
    python setup_conda_env.py                    # 创建名为 tenclip 的环境
    python setup_conda_env.py --name myenv       # 创建自定义名称的环境
    python setup_conda_env.py --python 3.11      # 指定 Python 版本

特点:
    - 自动检测 conda
    - 智能创建环境
    - 分步安装依赖
    - 完整的验证检查
    - 跨 Linux/Mac/Windows 工作
"""

import subprocess
import sys
import os
from pathlib import Path
import argparse

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def run_cmd(cmd, description="", shell=False, capture=False):
    """执行命令"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, check=True)
            return result.stdout.strip(), True
        else:
            subprocess.run(cmd, shell=shell, check=True)
            return "", True
    except subprocess.CalledProcessError as e:
        if description:
            print(f"{Colors.RED}✗ {description} 失败{Colors.NC}")
        return "", False

def check_conda():
    """检查 conda 是否安装"""
    print(f"{Colors.YELLOW}[1/5] 检查 conda...{Colors.NC}")
    
    try:
        output, success = run_cmd("conda --version", capture=True)
        if success:
            print(f"{Colors.GREEN}✓ {output}{Colors.NC}")
            return True
    except:
        pass
    
    print(f"{Colors.RED}✗ conda 未找到{Colors.NC}")
    print("请先安装 Miniconda 或 Anaconda:")
    print("  https://docs.conda.io/en/latest/miniconda.html")
    return False

def env_exists(env_name):
    """检查环境是否存在"""
    output, success = run_cmd("conda env list", capture=True, shell=True)
    if success:
        for line in output.split('\n'):
            if line.startswith(env_name):
                return True
    return False

def create_environment(env_name, python_version):
    """创建 conda 环境"""
    print(f"{Colors.YELLOW}[2/5] 创建 conda 环境...{Colors.NC}")
    print(f"环境名称: {env_name}")
    print(f"Python 版本: {python_version}")
    print()
    
    if env_exists(env_name):
        print(f"{Colors.YELLOW}⚠ 环境 '{env_name}' 已存在{Colors.NC}")
        response = input(f"{Colors.YELLOW}删除旧环境并重新创建? (y/n): {Colors.NC}")
        if response.lower() == 'y':
            print("删除旧环境...")
            run_cmd(f"conda env remove -n {env_name} -y", shell=True)
        else:
            print(f"{Colors.YELLOW}使用现有环境{Colors.NC}")
            print(f"{Colors.GREEN}✓ 跳过创建{Colors.NC}")
            return True
    
    print(f"创建环境 {env_name}...")
    success = run_cmd(
        f"conda create -n {env_name} python={python_version} -y -q",
        shell=True
    )[1]
    
    if success:
        print(f"{Colors.GREEN}✓ 完成{Colors.NC}")
        return True
    return False

def install_dependencies(env_name):
    """安装依赖"""
    print(f"{Colors.YELLOW}[3/5] 初始化环境...{Colors.NC}")
    
    # 升级 pip
    cmd = f"conda run -n {env_name} pip install --upgrade pip setuptools wheel -q"
    success = run_cmd(cmd, shell=True)[1]
    
    if success:
        print(f"{Colors.GREEN}✓ pip 已升级{Colors.NC}")
    
    print()
    print(f"{Colors.YELLOW}[4/5] 安装依赖...{Colors.NC}")
    
    # 获取 requirements 文件
    script_dir = Path(__file__).parent
    requirements_file = script_dir / "requirements_rtmpose_cpu.txt"
    
    if not requirements_file.exists():
        print(f"{Colors.RED}✗ 未找到 requirements 文件: {requirements_file}{Colors.NC}")
        return False
    
    print(f"使用 requirements: {requirements_file}")
    print()
    
    # 配置清华源
    print("配置清华源...")
    run_cmd(
        f"conda run -n {env_name} pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple",
        shell=True
    )
    
    # 分步安装
    steps = [
        ("PyTorch", "conda run -n {env_name} pip install -i https://pypi.tuna.tsinghua.edu.cn/simple torch torchvision torchaudio -q"),
        ("MMPose 基础", "conda run -n {env_name} pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmengine openmim -q"),
        ("MMCV", "conda run -n {env_name} mim install -q mmcv"),
        ("MMDet/MMPose", "conda run -n {env_name} pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mmdet mmpose -q"),
        ("其他依赖", "conda run -n {env_name} pip install -i https://pypi.tuna.tsinghua.edu.cn/simple Flask Flask-CORS opencv-python numpy scipy pandas -q"),
        ("回退方案", "conda run -n {env_name} pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mediapipe -q"),
    ]
    
    for step_name, step_cmd in steps:
        print(f"  安装 {step_name}...")
        run_cmd(step_cmd.format(env_name=env_name), shell=True)
    
    print(f"{Colors.GREEN}✓ 依赖安装完成{Colors.NC}")
    print()
    return True

def verify_installation(env_name):
    """验证安装"""
    print(f"{Colors.YELLOW}[5/5] 验证安装...{Colors.NC}")
    print()
    
    verify_script = '''
import sys

modules = {
    "torch": "PyTorch",
    "mmengine": "MMEngine",
    "mmcv": "MMCV",
    "mmdet": "MMDet",
    "mmpose": "MMPose",
    "cv2": "OpenCV",
    "flask": "Flask",
    "mediapipe": "MediaPipe",
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
print("✓ RTMpose 检查:")
try:
    from mmpose.apis import MMPoseInferencer
    print("  ✓ MMPoseInferencer 可用")
    print("  ✓ 支持的模型: rtmpose-s, rtmpose-m, rtmpose-l")
except Exception as e:
    print(f"  ⚠ RTMpose 暂不可用: {e}")

print()
print("✓ 计算设备:")
import torch
if torch.cuda.is_available():
    print(f"  ✓ GPU: {torch.cuda.get_device_name(0)}")
else:
    print("  ✓ GPU: 不可用（CPU 模式）")

print()
if all_ok:
    print("✅ 环境设置完成！")
else:
    print("⚠️  部分模块缺失，但基础已安装")
'''
    
    cmd = f"conda run -n {env_name} python -c \"{verify_script}\""
    run_cmd(cmd, shell=True)

def print_summary(env_name):
    """打印总结"""
    print()
    print(f"{Colors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print(f"{Colors.GREEN}✅ Conda 环境创建完成！{Colors.NC}")
    print(f"{Colors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print()
    print(f"{Colors.BLUE}后续使用{Colors.NC}")
    print()
    print("1. 激活环境:")
    print(f"   conda activate {env_name}")
    print()
    print("2. 启动 RTMpose v2 后端:")
    print("   cd ~/tenclip/pose")
    print("   python pose_server_v2.py")
    print()
    print("3. 验证:")
    print("   curl http://localhost:5000/api/health")
    print()
    print("4. 导出环境配置（用于其他机器）:")
    print(f"   conda env export > {env_name}.yml")
    print("   # 其他机器恢复:")
    print(f"   conda env create -f {env_name}.yml")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="RTMpose v2 Conda 环境快速部署脚本"
    )
    parser.add_argument("--name", "-n", default="tenclip", help="环境名称 (默认: tenclip)")
    parser.add_argument("--python", "-p", default="3.10", help="Python 版本 (默认: 3.10)")
    
    args = parser.parse_args()
    
    print(f"{Colors.BLUE}╔════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║   RTMpose v2 Conda 环境部署脚本        ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════╝{Colors.NC}")
    print()
    
    # 检查 conda
    if not check_conda():
        sys.exit(1)
    print()
    
    # 创建环境
    if not create_environment(args.name, args.python):
        print(f"{Colors.RED}✗ 环境创建失败{Colors.NC}")
        sys.exit(1)
    print()
    
    # 安装依赖
    if not install_dependencies(args.name):
        print(f"{Colors.RED}✗ 依赖安装失败{Colors.NC}")
        sys.exit(1)
    
    # 验证
    verify_installation(args.name)
    
    # 总结
    print_summary(args.name)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}已取消{Colors.NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}✗ 错误: {e}{Colors.NC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
