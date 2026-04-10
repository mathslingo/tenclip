import sys
import os
sys.path.insert(0, '.')
import tempfile
import time
from moviepy.video.VideoClip import ColorClip

# 创建虚拟视频文件
def create_dummy_video(duration=5, filename=None):
    if filename is None:
        filename = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name
    clip = ColorClip((640, 480), color=(255, 0, 0), duration=duration)
    clip.write_videofile(filename, fps=24, codec='libx264', audio_codec='aac')
    clip.close()
    return filename

# 模拟 gr.File 对象
class MockFile:
    def __init__(self, path):
        self.name = path

# 导入 app 的 trim_video 函数
from app import trim_video

def test_trim():
    print("Creating dummy video...")
    video_path = create_dummy_video(duration=10)
    print(f"Video created: {video_path}")
    
    try:
        mock_file = MockFile(video_path)
        start = 2
        end = 5
        print(f"Trimming from {start} to {end}...")
        output = trim_video(mock_file, start, end)
        if output:
            print(f"Success! Output saved to: {output}")
            # 检查输出文件是否存在
            if os.path.exists(output):
                print("Output file exists.")
                # 清理
                os.unlink(output)
            else:
                print("ERROR: Output file not found!")
        else:
            print("ERROR: trim_video returned None")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理输入视频
        if os.path.exists(video_path):
            os.unlink(video_path)
    
    print("Test completed.")

if __name__ == "__main__":
    test_trim()