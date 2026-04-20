"""Gradio H5 风格页：上传视频 + 指导意见（与 front_page 配色接近）。"""

from __future__ import annotations

import os

import gradio as gr

from services.vlm_tennis import (
    MAX_VIDEO_DURATION_SEC,
    analyze_tennis_video,
    prompt_profile_radio_choices,
    vlm_dependency_message,
)

PERF_MAP = {
    "省显存（弱显卡推荐）": "eco",
    "平衡": "balanced",
    "质量优先（显存充足）": "quality",
}


def _extract_video_path(video_file):
    if video_file is None:
        return None
    if isinstance(video_file, str):
        return video_file
    if isinstance(video_file, dict):
        return video_file.get("path")
    if hasattr(video_file, "name"):
        return video_file.name
    return None


def _run_analysis(video_file, perf_label, prompt_profile, progress=gr.Progress()):
    path = _extract_video_path(video_file)
    if not path:
        return "请先上传视频文件。"
    if not os.path.exists(path):
        return f"视频文件不存在: {path}"
    hint = vlm_dependency_message()
    if hint:
        return hint
    mode = PERF_MAP.get(perf_label, "eco")
    pp = (prompt_profile or "").strip() or None
    progress(0.05, desc="检查视频与依赖…")
    progress(0.2, desc="抽帧 / 推理中…")
    out = analyze_tennis_video(path, mode, prompt_profile=pp)
    progress(1.0, desc="完成")
    return out


# 与 pages/front_page 一致的浅灰底 + 薄荷绿主色（覆盖 Gradio 默认）
VIDEO_INPUT_CSS = """
.gradio-container { max-width: min(100%, 520px) !important; margin-left: auto !important; margin-right: auto !important; }
.gradio-app { background: #f2f3f5 !important; }
#vi-hero {
  background: linear-gradient(145deg, #baf5e8, #d4fff4);
  border-radius: 16px;
  padding: 14px 16px;
  margin-bottom: 8px;
  border: none;
}
#vi-hero h1 { margin: 0; font-size: 1.35rem; font-weight: 700; color: #151821; }
#vi-hero p { margin: 6px 0 0; font-size: 0.85rem; color: #415360; }
#vi-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 12px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.06);
}
button.primary {
  background: linear-gradient(140deg, #3bf0bf, #13d8a8) !important;
  border: none !important;
  border-radius: 10px !important;
}
textarea, .scroll-hide {
  border-radius: 10px !important;
}
"""

with gr.Blocks(
    title="TenniTi · 视频分析",
    css=VIDEO_INPUT_CSS,
    theme=gr.themes.Soft(
        radius_size=gr.themes.sizes.radius_md,
        spacing_size=gr.themes.sizes.spacing_md,
    ),
) as video_input_demo:
    gr.Markdown(
        "<div id='vi-hero'><h1>TenniTi · 动作分析</h1>"
        "<p>上传网球视频，生成简要指导建议（与主站同一套视频理解逻辑）。"
        f" 默认只分析前约 {int(MAX_VIDEO_DURATION_SEC)} 秒。</p></div>"
    )
    with gr.Column(elem_id="vi-card"):
        video = gr.File(
            label="上传视频",
            file_types=[".mp4", ".mov", ".avi"],
        )
        perf = gr.Radio(
            choices=list(PERF_MAP.keys()),
            value="省显存（弱显卡推荐）",
            label="显存 / 质量",
        )
        prompt_prof = gr.Radio(
            choices=prompt_profile_radio_choices(),
            value="default",
            label="分析提示词（覆盖 TENCLIP_PROMPT_PROFILE）",
        )
        submit = gr.Button("开始分析", variant="primary")
        guidance = gr.Textbox(
            label="指导意见",
            lines=14,
            max_lines=24,
            placeholder="分析结果将显示在这里",
        )
    submit.click(_run_analysis, inputs=[video, perf, prompt_prof], outputs=guidance)
