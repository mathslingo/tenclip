import sys
import os
sys.path.insert(0, '.')
import tempfile
from moviepy.video.VideoClip import ColorClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from app import trim_video

# 模拟 gr.File 对象
class MockFile:
    def __init__(self, path):
        self.name = path

def create_dummy_video(duration=5):
    """创建虚拟视频文件并返回路径，确保文件已关闭"""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        video_path = f.name
    
    # 使用 ColorClip 创建简单视频
    clip = ColorClip((640, 480), color=(255, 0, 0), duration=duration)
    clip.write_videofile(video_path, fps=24, codec='libx264', audio_codec='aac')
    clip.close()
    return video_path

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
            if os.path.exists(output):
                print("Output file exists.")
                # 验证输出视频时长
                with VideoFileClip(output) as out_clip:
                    out_duration = out_clip.duration
                    print(f"Output duration: {out_duration}")
                    expected = end - start
                    if abs(out_duration - expected) < 0.1:
                        print("Duration matches expected!")
                    else:
                        print(f"WARNING: Duration mismatch: expected {expected}, got {out_duration}")
                # 清理输出文件
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
            try:
                os.unlink(video_path)
            except Exception as e:
                print(f"Warning: could not delete {video_path}: {e}")
    
    print("Test completed.")

if __name__ == "__main__":
    test_trim()