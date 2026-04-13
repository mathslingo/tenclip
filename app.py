import logging
import os
import tempfile

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import gradio as gr
from moviepy.video.io.VideoFileClip import VideoFileClip

from services.vlm_tennis import (
    MAX_VIDEO_DURATION_SEC,
    analyze_tennis_video,
    vlm_dependency_message,
)

logging.basicConfig(level=logging.INFO)
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

PERF_MAP = {
    "省显存（弱显卡推荐）": "eco",
    "平衡": "balanced",
    "质量优先（显存充足）": "quality",
}


def _extract_video_path(video_file):
    """Support Gradio file values across versions."""
    if video_file is None:
        return None
    if isinstance(video_file, str):
        return video_file
    if isinstance(video_file, dict):
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


def run_tennis_analysis(video_file, perf_label, progress=gr.Progress()):
    path = _extract_video_path(video_file)
    if not path:
        return "请先上传视频文件。"
    hint = vlm_dependency_message()
    if hint:
        return hint
    mode = PERF_MAP.get(perf_label, "eco")
    progress(0.05, desc="检查视频与依赖…")
    progress(0.15, desc="抽帧 / 加载模型（首次会下载权重，请耐心等待）…")
    out = analyze_tennis_video(path, mode)
    progress(1.0, desc="完成")
    return out


def _vlm_tab_intro():
    dep = vlm_dependency_message()
    base = (
        f"使用 **Qwen2-VL-2B-Instruct**（约 2B）对视频均匀抽帧做视觉理解，"
        f"输出动作是否大致合理及初学者的改进建议。\n\n"
        f"- **推理框架**：优先 **LLaMA-Factory** `ChatModel`（`TENCLIP_INFER_BACKEND=auto`），失败时回退 **Transformers**。\n"
        "- **权重下载**：默认 **ModelScope**（`TENCLIP_MODEL_DOWNLOAD_SOURCE=modelscope`）；HF 不可用时不必改镜像。\n"
        f"- **时长**：仅分析前 **{int(MAX_VIDEO_DURATION_SEC)} 秒**（约 5 分钟）；更长请先剪辑。\n"
        "- **省显存 / 平衡 / 质量**：帧数与分辨率递增，弱显卡请保持「省显存」。\n"
        "- 首次分析前建议运行 `download-vlm-conda.bat` 预下载权重。\n"
    )
    if dep:
        return (
            base
            + "\n**当前环境未安装分析依赖。** Conda：`setup-conda-env.bat`；或 pip："
            + "`pip install -r requirements-llm.txt -r requirements-llm-lf.txt`。\n"
        )
    return base + "\n依赖已就绪，可直接点击「开始分析」。\n"


with gr.Blocks(title="TenClip") as demo:
    gr.Markdown("# TenClip：网球视频剪辑与动作分析")

    with gr.Tabs():
        with gr.Tab("视频剪辑"):
            gr.Markdown("上传视频，按秒裁剪并下载片段。")
            with gr.Row():
                trim_file = gr.File(label="上传视频 (MP4/MOV/AVI)", file_types=[".mp4", ".mov", ".avi"])
                t_start = gr.Number(label="开始时间（秒）", value=0)
                t_end = gr.Number(label="结束时间（秒）", value=10)
            trim_btn = gr.Button("剪辑并下载", variant="primary")
            trim_out = gr.File(label="剪辑结果")

            trim_btn.click(trim_video, inputs=[trim_file, t_start, t_end], outputs=trim_out)

        with gr.Tab("网球动作分析（大模型）"):
            tennis_intro = gr.Markdown(_vlm_tab_intro())
            with gr.Row():
                tennis_file = gr.File(label="上传网球视频", file_types=[".mp4", ".mov", ".avi"])
                perf = gr.Radio(
                    list(PERF_MAP.keys()),
                    value="省显存（弱显卡推荐）",
                    label="显存 / 质量模式",
                )
            tennis_btn = gr.Button("开始分析", variant="primary")
            tennis_out = gr.Markdown()

            tennis_btn.click(run_tennis_analysis, inputs=[tennis_file, perf], outputs=tennis_out)

            gr.Markdown(
                "**弱显卡建议**：保持「省显存」；若仍 OOM，可先剪辑更短片段，"
                "或在启动前设置环境变量 `TENCLIP_FORCE_CPU=1` 强制走 CPU（会慢很多）。"
            )

def main() -> None:
    port = int(os.environ.get("GRADIO_SERVER_PORT", "7861"))
    host = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")
    demo.launch(server_name=host, server_port=port)


if __name__ == "__main__":
    main()
