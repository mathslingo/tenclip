"""推理与路径校验（同步，在线程池中执行）。"""

from __future__ import annotations

import base64
import os
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image

from services.vlm_tennis import (
    PROMPT_PROFILES,
    analyze_tennis_video,
    infer_backend_choice,
    infer_vision_chat,
    resolve_prompt_profile,
    vlm_dependency_message,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def allowed_data_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("TENCLIP_VLM_API_DATA_ROOT", "TENCLIP_UPLOAD_DIR"):
        raw = os.environ.get(key, "").strip()
        if raw:
            roots.append(Path(raw).resolve())
    roots.append((_REPO_ROOT / "data").resolve())
    roots.append((_REPO_ROOT / "data" / "uploads").resolve())
    unique: list[Path] = []
    for p in roots:
        if p not in unique:
            unique.append(p)
    return unique


def resolve_safe_video_path(video_path: str) -> Path:
    p = Path(video_path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"视频不存在: {p}")
    for root in allowed_data_roots():
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise PermissionError(
        "video_path 须在 data/ 或 uploads/ 下；"
        "可设置 TENCLIP_VLM_API_DATA_ROOT 扩大允许目录"
    )


def decode_image_b64(data: str) -> Image.Image:
    raw = (data or "").strip()
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        buf = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError(f"images_base64 解码失败: {exc}") from exc
    im = Image.open(BytesIO(buf))
    return im.convert("RGB")


def model_status() -> dict:
    hint = vlm_dependency_message()
    if hint:
        return {"model_ready": False, "backend": "", "model_path": "", "error": hint}
    ok, backend, err = infer_backend_choice()
    if not ok:
        return {"model_ready": False, "backend": "", "model_path": "", "error": err}
    from services.model_resolve import get_local_model_dir

    try:
        model_path = str(get_local_model_dir())
    except Exception as exc:
        return {"model_ready": False, "backend": backend, "model_path": "", "error": str(exc)}
    return {"model_ready": True, "backend": backend, "model_path": model_path, "error": ""}


def run_chat(
    prompt: str,
    *,
    system_prompt: str | None,
    images_base64: list[str],
    perf_mode: str,
    max_new_tokens: int | None,
) -> str:
    images = [decode_image_b64(b) for b in images_base64]
    return infer_vision_chat(
        images,
        prompt,
        mode=perf_mode,  # type: ignore[arg-type]
        max_new_tokens=max_new_tokens,
        system_prompt=system_prompt,
    )


def run_analyze_upload(
    upload_bytes: bytes,
    suffix: str,
    perf_mode: str,
    prompt_profile: str | None,
) -> str:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(upload_bytes)
        path = tmp.name
    try:
        pp = resolve_prompt_profile(prompt_profile)
        return analyze_tennis_video(path, perf_mode, prompt_profile=pp)  # type: ignore[arg-type]
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_analyze_path(video_path: str, perf_mode: str, prompt_profile: str) -> tuple[str, str]:
    safe = resolve_safe_video_path(video_path)
    pp = resolve_prompt_profile(prompt_profile)
    guidance = analyze_tennis_video(str(safe), perf_mode, prompt_profile=pp)  # type: ignore[arg-type]
    return guidance, pp


def list_prompt_profiles() -> list[str]:
    return list(PROMPT_PROFILES.keys())
