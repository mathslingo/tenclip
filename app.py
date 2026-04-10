import gradio as gr
from moviepy.video.io.VideoFileClip import VideoFileClip
import tempfile
import os
import logging
logging.basicConfig(level=logging.INFO)
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"


def _extract_video_path(video_file):
    """Support Gradio file values across versions."""
    if video_file is None:
        return None
    if isinstance(video_file, str):
        return video_file
    if isinstance(video_file, dict):
        # Some versions may return {"path": "...", ...}
        return video_file.get("path")
    if hasattr(video_file, "name"):
        return video_file.name
    return None


def trim_video(video_file, start_time, end_time):
    clip = None
    subclip = None
    try:
        video_path = _extract_video_path(video_file)
        if not video_path:
            raise ValueError("请先上传视频文件")
        if not os.path.exists(video_path):
            raise ValueError(f"视频文件不存在: {video_path}")

        start_time = float(start_time)
        end_time = float(end_time)

        clip = VideoFileClip(video_path)
        start_time = max(0, start_time)
        end_time = min(end_time, clip.duration)
        if end_time <= start_time:
            raise ValueError("结束时间必须大于开始时间")

        # moviepy v1: subclip; moviepy v2: subclipped
        if hasattr(clip, "subclipped"):
            subclip = clip.subclipped(start_time, end_time)
        else:
            subclip = clip.subclip(start_time, end_time)

        output_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        subclip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        return output_path
    except Exception as e:
        raise gr.Error(f"剪辑失败: {str(e)}")
    finally:
        if subclip is not None:
            subclip.close()
        if clip is not None:
            clip.close()

iface = gr.Interface(
    fn=trim_video,
    inputs=[
        gr.File(label="上传视频 (MP4/MOV/AVI)", file_types=[".mp4", ".mov", ".avi"]),
        gr.Number(label="开始时间（秒）", value=0),
        gr.Number(label="结束时间（秒）", value=10)
    ],
    outputs=gr.File(label="下载剪辑后的视频"),
    title="🎬 视频剪辑助手",
    description="上传视频文件，输入开始和结束时间（秒），点击剪辑即可下载片段。"
)

if __name__ == "__main__":
    iface.launch(server_port=7860)