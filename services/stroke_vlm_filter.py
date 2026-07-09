"""用 VLM 对击球候选片段做二次过滤（是否处于比赛/击球回合）。"""

from __future__ import annotations

import io
import logging
import subprocess
from typing import Any, Callable

from PIL import Image

from services.stroke_detect import StrokeSegment, ffmpeg_path

logger = logging.getLogger(__name__)

_RALLY_PROMPT = (
    "这些图像来自同一段网球视频。请判断：画面中是否处于**比赛回合或击球动作**中"
    "（例如挥拍、对拉、发球、接发），而不是休息、换边、捡球、空场等待。"
    "只回答一个字：是 或 否。"
)


def _extract_frame_jpeg(video_path: str, t_sec: float, max_side: int = 384) -> Image.Image | None:
    cmd = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, t_sec):.3f}",
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-vf",
        f"scale={max_side}:-2",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=120)
        if out.returncode != 0 or not out.stdout:
            return None
        return Image.open(io.BytesIO(out.stdout)).convert("RGB")
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("frame extract failed t=%.2f: %s", t_sec, e)
        return None


def _segment_sample_times(seg: StrokeSegment, n: int = 2) -> list[float]:
    if n <= 1:
        return [seg.start + seg.duration() * 0.5]
    dur = max(seg.duration(), 0.05)
    return [seg.start + dur * (i + 1) / (n + 1) for i in range(n)]


def _parse_yes_no(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True  # 不确定时保留，避免误删
    if t.startswith("否") or t.startswith("no") or "不是" in t or "等待" in t:
        return False
    if t.startswith("是") or t.startswith("yes") or "是的" in t:
        return True
    return True


def classify_segment_with_vlm(
    video_path: str,
    seg: StrokeSegment,
    *,
    perf_mode: str = "eco",
    frames_per_segment: int = 2,
) -> tuple[bool, str]:
    """对单个片段抽帧并用 VLM 判断是否保留。返回 (keep, raw_reply_snippet)。"""
    from services.model_resolve import get_local_model_dir
    from services.vlm_tennis import Mode, _get_lf_chat

    times = _segment_sample_times(seg, frames_per_segment)
    images: list[Any] = []
    for t in times:
        im = _extract_frame_jpeg(video_path, t)
        if im is not None:
            images.append(im)
    if not images:
        return True, "(无帧，保留)"

    local_dir = get_local_model_dir()
    mode: Mode = perf_mode if perf_mode in ("eco", "balanced", "quality") else "eco"
    chat = _get_lf_chat(local_dir, mode)
    messages = [{"role": "user", "content": _RALLY_PROMPT}]
    try:
        responses = chat.chat(messages, images=images, max_new_tokens=16)
        reply = (responses[0].response_text or "").strip()
    except Exception as e:
        logger.warning("VLM classify failed: %s", e)
        return True, f"(VLM 失败，保留: {e})"
    keep = _parse_yes_no(reply)
    return keep, reply[:80]


def vlm_filter_segments(
    video_path: str,
    segments: list[StrokeSegment],
    *,
    perf_mode: str = "eco",
    max_segments: int = 80,
    frames_per_segment: int = 2,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[StrokeSegment], dict[str, Any]]:
    """VLM 二次过滤；段数过多时只处理前 max_segments 段（按 score 降序）。"""
    if not segments:
        return [], {"vlm_filtered": 0, "vlm_dropped": 0}

    ranked = sorted(segments, key=lambda s: s.score, reverse=True)
    if len(ranked) > max_segments:
        to_check = ranked[:max_segments]
        rest = ranked[max_segments:]
    else:
        to_check = ranked
        rest = []

    kept: list[StrokeSegment] = []
    dropped = 0
    details: list[dict[str, Any]] = []

    for i, seg in enumerate(to_check):
        if progress:
            progress(f"VLM 过滤 {i + 1}/{len(to_check)} …")
        keep, snippet = classify_segment_with_vlm(
            video_path,
            seg,
            perf_mode=perf_mode,
            frames_per_segment=frames_per_segment,
        )
        details.append({"start": seg.start, "end": seg.end, "keep": keep, "reply": snippet})
        if keep:
            kept.append(seg)
        else:
            dropped += 1

    kept.extend(rest)
    kept.sort(key=lambda s: s.start)
    return kept, {
        "vlm_checked": len(to_check),
        "vlm_kept": len(kept) - len(rest),
        "vlm_dropped": dropped,
        "vlm_skipped_rest": len(rest),
        "details": details[:30],
    }
