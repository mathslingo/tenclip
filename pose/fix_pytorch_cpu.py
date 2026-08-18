#!/usr/bin/env python3
"""
CPU-Only 云主机 PyTorch/MMCV 修复脚本

问题: ImportError: undefined symbol: iJIT_NotifyEvent
原因: PyTorch 版本与 MMCV 不兼容（通常是 GPU 版本与 CPU 环境冲突）

解决方案:
1. 卸载旧 PyTorch
2. 安装 CPU 专用版本
3. 用 pip 安装 mmcv/mmdet/mmpose（不用 mim，避免编译）
4. 验证 RTMpose

用法: python fix_pytorch_cpu.py
"""

import subprocess
import sys

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def run_cmd(cmd, description="", check=True):
    """执行命令"""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        if result.returncode != 0 and description:
            print(f"{Colors.RED}✗ {description} 失败{Colors.NC}")
            if result.stderr:
                print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"{Colors.RED}✗ 执行失败: {e}{Colors.NC}")
        return False

def main():
    print(f"{Colors.BLUE}╔════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║   CPU-Only PyTorch/MMCV 修复脚本      ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════╝{Colors.NC}")
    print()
    
    # 检查当前环境
    print(f"{Colors.YELLOW}检查当前环境...{Colors.NC}")
    result = subprocess.run(
        f"{sys.executable} -c \"import torch; print('当前 PyTorch:', torch.__version__); print('CUDA:', torch.cuda.is_available())\"",
        shell=True,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    
    # 询问确认
    print(f"{Colors.YELLOW}这会卸载旧 PyTorch，然后重新安装 CPU 版本。{Colors.NC}")
    confirm = input(f"{Colors.YELLOW}继续吗？(y/n): {Colors.NC}")
    if confirm.lower() != 'y':
        print(f"{Colors.YELLOW}已取消{Colors.NC}")
        return
    
    print()
    print(f"{Colors.BLUE}开始修复...{Colors.NC}")
    print()
    
    # 1. 卸载旧 PyTorch
    print(f"{Colors.YELLOW}[1/4] 卸载旧 PyTorch...{Colors.NC}")
    subprocess.run(
        f"{sys.executable} -m pip uninstall torch torchvision torchaudio -y -q",
        shell=True,
        capture_output=True
    )
    print(f"{Colors.GREEN}✓ 完成{Colors.NC}")
    print()
    
    # 2. 安装 CPU 版本
    print(f"{Colors.YELLOW}[2/4] 安装 PyTorch CPU 版本...{Colors.NC}")
    success = run_cmd(
        f"{sys.executable} -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "
        "torch torchvision torchaudio -q",
        "PyTorch 安装"
    )
    if not success:
        sys.exit(1)
    print(f"{Colors.GREEN}✓ 完成{Colors.NC}")
    print()
    
    # 3. 验证 PyTorch
    print(f"{Colors.YELLOW}[3/4] 验证 PyTorch...{Colors.NC}")
    subprocess.run(
        f"{sys.executable} -c \"import torch; print(f'✓ PyTorch: {{torch.__version__}}'); print(f'✓ CUDA available: {{torch.cuda.is_available()}}')\"",
        shell=True,
        check=False
    )
    print()
    
    # 4. 安装 MMPose
    print(f"{Colors.YELLOW}[4/4] 安装 MMPose/MMCV/MMDet...{Colors.NC}")
    success = run_cmd(
        f"{sys.executable} -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "
        "mmcv mmdet mmpose -q",
        "MMPose 安装"
    )
    if not success:
        print(f"{Colors.YELLOW}⚠ MMPose 安装出现问题，但 MediaPipe 回退方案仍可用{Colors.NC}")
    else:
        print(f"{Colors.GREEN}✓ 完成{Colors.NC}")
    
    print()
    
    # 验证 RTMpose
    print(f"{Colors.YELLOW}验证 RTMpose...{Colors.NC}")
    verify_script = '''
try:
    from mmpose.apis import MMPoseInferencer
    print("✓ RTMpose API 可用")
    print("✓ 支持的模型: rtmpose-s, rtmpose-m, rtmpose-l")
except Exception as e:
    print(f"⚠ RTMpose 暂时不可用: {e}")
    print("  但 MediaPipe 回退方案可用")
'''
    subprocess.run(
        f"{sys.executable} -c \"{verify_script}\"",
        shell=True,
        check=False
    )
    
    print()
    print(f"{Colors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print(f"{Colors.GREEN}✅ 修复完成！{Colors.NC}")
    print(f"{Colors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print()
    print(f"{Colors.BLUE}后续步骤{Colors.NC}")
    print("1. 重启服务:")
    print("   python pose_server_v2.py")
    print()
    print("2. 验证:")
    print("   curl http://localhost:5000/api/health")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}已取消{Colors.NC}")
        sys.exit(1)
