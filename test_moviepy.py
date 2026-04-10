import sys
sys.path.insert(0, '.')
from moviepy.video.io.VideoFileClip import VideoFileClip
import tempfile
import os

# 创建一个简单的测试：检查导入和基本功能
print("Testing moviepy...")
try:
    # 检查是否可以创建虚拟剪辑（不需要实际文件）
    from moviepy.editor import VideoClip
    import numpy as np
    
    # 创建一个简单的彩色剪辑
    def make_frame(t):
        return np.array([[255, 0, 0]], dtype=np.uint8)
    
    clip = VideoClip(make_frame, duration=1)
    print("VideoClip creation succeeded")
    
    # 测试subclip方法
    subclip = clip.subclip(0, 0.5)
    print("subclip method exists")
    
    # 测试VideoFileClip类
    print("VideoFileClip class available")
    
    # 检查ffmpeg可用性
    from moviepy.config import get_setting
    ffmpeg_binary = get_setting("FFMPEG_BINARY")
    print(f"FFMPEG binary: {ffmpeg_binary}")
    
    # 尝试通过imageio-ffmpeg查找
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"imageio_ffmpeg path: {ffmpeg_path}")
    except Exception as e:
        print(f"imageio_ffmpeg not found: {e}")
    
    print("All tests passed")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()