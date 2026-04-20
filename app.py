import logging
import os
import shutil
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# 仓库在 ~/code/tenclip 等任意路径时：若存在本地权重目录，优先直接推理（不再走远程下载）
_REPO_ROOT = Path(__file__).resolve().parent
_LOCAL_VLM = _REPO_ROOT / "model" / "Qwen2-VL-2B-Instruct"
if not os.environ.get("TENCLIP_VLM_MODEL", "").strip() and _LOCAL_VLM.is_dir():
    os.environ["TENCLIP_VLM_MODEL"] = str(_LOCAL_VLM)

import gradio as gr
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from moviepy.video.io.VideoFileClip import VideoFileClip

from pages.video_input.gradio_page import video_input_demo

from services.vlm_tennis import (
    MAX_VIDEO_DURATION_SEC,
    analyze_tennis_video,
    format_guidance_markdown,
    prompt_profile_radio_choices,
    resolve_prompt_profile,
    vlm_dependency_message,
)

logging.basicConfig(level=logging.INFO)
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

PERF_MAP = {
    "省显存（弱显卡推荐）": "eco",
    "平衡": "balanced",
    "质量优先（显存充足）": "quality",
}

MOBILE_EVENTS = [
    {
        "id": "evt-101",
        "title": "午间小团课【正手进阶】1号+2号场",
        "timeText": "明天(周三)下午12点 · 1.5小时",
        "locationText": "闵行区吴中路485号古北 · 室内 · 6.4km",
        "joined": 1,
        "capacity": 5,
        "levelMin": 1.0,
        "levelMax": 5.0,
        "playType": "不限",
        "distanceKm": 6.4,
        "startTimestamp": 1765560000,
        "hotScore": 98,
    },
    {
        "id": "evt-102",
        "title": "晨间2小时畅打【4号场】",
        "timeText": "明天(周三)上午8点 · 2小时",
        "locationText": "闵行区吴中路485号古北 · 室内 · 6.4km",
        "joined": 1,
        "capacity": 2,
        "levelMin": 1.0,
        "levelMax": 5.0,
        "playType": "不限",
        "distanceKm": 6.4,
        "startTimestamp": 1765545600,
        "hotScore": 88,
    },
    {
        "id": "evt-103",
        "title": "周日晚 OMC 5.0 双打比赛局",
        "timeText": "本周日晚上8点 · 2小时",
        "locationText": "徐汇区天钥桥路 · 室内 · 4.0km",
        "joined": 2,
        "capacity": 16,
        "levelMin": 2.0,
        "levelMax": 3.0,
        "playType": "双打",
        "distanceKm": 4.0,
        "startTimestamp": 1765800000,
        "hotScore": 76,
    },
]


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


def run_tennis_analysis(video_file, perf_label, prompt_profile, progress=gr.Progress()):
    path = _extract_video_path(video_file)
    if not path:
        return "请先上传视频文件。"
    hint = vlm_dependency_message()
    if hint:
        return hint
    mode = PERF_MAP.get(perf_label, "eco")
    pp = (prompt_profile or "").strip() or None
    progress(0.05, desc="检查视频与依赖…")
    progress(0.15, desc="抽帧 / 加载模型（首次会下载权重，请耐心等待）…")
    out = analyze_tennis_video(path, mode, prompt_profile=pp)
    progress(1.0, desc="完成")
    return format_guidance_markdown(out)


def run_mobile_api_analysis(video_path: str, perf_mode: str, prompt_profile: str | None = None) -> str:
    hint = vlm_dependency_message()
    if hint:
        raise ValueError(hint)
    pp = (prompt_profile or "").strip() or None
    return analyze_tennis_video(video_path, perf_mode, prompt_profile=pp)


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


TENNIS_GUIDANCE_CSS = """
#tennis-guidance {
  font-size: 0.95rem;
  line-height: 1.55;
  color: #1a1f26;
  text-align: left;
}
#tennis-guidance h2 { margin: 0 0 0.5em; font-size: 1.12rem; color: #0d3d32; border-bottom: 1px solid #e5ebe9; padding-bottom: 0.35em; }
#tennis-guidance h3, #tennis-guidance h4 { margin: 0.85em 0 0.35em; font-size: 1.02rem; color: #243240; }
#tennis-guidance p { margin: 0.45em 0; }
#tennis-guidance ul, #tennis-guidance ol { margin: 0.35em 0 0.55em; padding-left: 1.35em; }
#tennis-guidance li { margin: 0.22em 0; }
#tennis-guidance pre {
  background: #f4f6f9;
  border: 1px solid #e5e9f0;
  border-radius: 10px;
  padding: 10px 12px;
  overflow-x: auto;
  font-size: 0.8rem;
  line-height: 1.45;
}
#tennis-guidance details { margin-top: 1rem; border-radius: 12px; border: 1px solid #e5e9f0; padding: 8px 10px; background: #fafbfc; }
#tennis-guidance summary { cursor: pointer; font-size: 0.9rem; color: #415360; }
#tennis-guidance hr { border: 0; border-top: 1px solid #e8ecf1; margin: 1em 0; }
#tennis-guidance code { background: #eef2f6; padding: 0.12em 0.35em; border-radius: 4px; font-size: 0.88em; }
"""


with gr.Blocks(title="TenClip", css=TENNIS_GUIDANCE_CSS) as demo:
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
            gr.Markdown(_vlm_tab_intro())
            with gr.Row():
                tennis_file = gr.File(label="上传网球视频", file_types=[".mp4", ".mov", ".avi"])
                perf = gr.Radio(
                    list(PERF_MAP.keys()),
                    value="省显存（弱显卡推荐）",
                    label="显存 / 质量模式",
                )
            prompt_prof = gr.Radio(
                choices=prompt_profile_radio_choices(),
                value="default",
                label="分析提示词版本",
            )
            tennis_btn = gr.Button("开始分析", variant="primary")
            tennis_out = gr.Markdown(
                elem_id="tennis-guidance",
            )

            tennis_btn.click(
                run_tennis_analysis,
                inputs=[tennis_file, perf, prompt_prof],
                outputs=tennis_out,
            )

            gr.Markdown(
                "**弱显卡建议**：保持「省显存」；若仍 OOM，可先剪辑更短片段，"
                "或在启动前设置环境变量 `TENCLIP_FORCE_CPU=1` 强制走 CPU（会慢很多）。"
            )


def create_app() -> FastAPI:
    api = FastAPI(title="TenClip API")

    # 主 Gradio 若挂在 path="/"，会注册 Mount("/") 抢走所有子路径（含 /video_input），故主界面改挂 /gradio。
    @api.get("/", include_in_schema=False)
    def root_to_gradio():
        return RedirectResponse(url="/gradio/", status_code=302)

    @api.get("/api/mobile/events")
    def mobile_events():
        return {"events": MOBILE_EVENTS}

    @api.post("/api/mobile/analyze-video")
    async def mobile_analyze_video(
        video: UploadFile = File(...),
        perf_mode: str = Form("eco"),
        prompt_profile: str = Form(""),
    ):
        suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
        temp_path = Path(tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name)
        try:
            with temp_path.open("wb") as out_file:
                shutil.copyfileobj(video.file, out_file)
            pp = prompt_profile.strip() or None
            guidance = run_mobile_api_analysis(
                str(temp_path), perf_mode=perf_mode, prompt_profile=pp
            )
            return {
                "guidance": guidance,
                "perf_mode": perf_mode,
                "prompt_profile": resolve_prompt_profile(pp),
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"分析失败: {exc}") from exc
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                logging.exception("Failed to cleanup temp file: %s", temp_path)
            await video.close()

    front_page_dir = _REPO_ROOT / "pages" / "front_page"
    if front_page_dir.exists():
        # 独立 Web 入口（响应式：PC/手机皆可）；静态资源走独立前缀，避免与 Gradio 根路由冲突。
        api.mount("/web-assets", StaticFiles(directory=str(front_page_dir)), name="web-assets")

        @api.get("/web")
        @api.get("/web/")
        def web_home():
            return FileResponse(front_page_dir / "index.html")

        # 兼容旧地址：/mobile -> /web
        @api.get("/mobile")
        @api.get("/mobile/")
        def mobile_home():
            return FileResponse(front_page_dir / "index.html")

    # 简单 H5（Gradio）：上传视频 + 指导意见，风格贴近 front_page（须在主界面 /gradio 之前注册，避免被吞）
    gr.mount_gradio_app(api, video_input_demo, path="/video_input")

    return gr.mount_gradio_app(api, demo, path="/gradio")


def main() -> None:
    port = int(os.environ.get("GRADIO_SERVER_PORT", "7861"))
    host = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
