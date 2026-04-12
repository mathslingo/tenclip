"""
网球视频抽帧 + 视觉语言模型分析。

- 权重获取：默认 **ModelScope**（`TENCLIP_MODEL_DOWNLOAD_SOURCE=modelscope`），避免 Hugging Face 不可达。
- 推理框架：默认 **LLaMA-Factory** `ChatModel`（`TENCLIP_INFER_BACKEND=auto|llamafactory|transformers`），
  不可用时回退到原生 Transformers + qwen_vl_utils。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Literal, Tuple

from moviepy.video.io.VideoFileClip import VideoFileClip

from services.model_resolve import default_remote_model_id, download_source, get_local_model_dir

logger = logging.getLogger(__name__)

MAX_VIDEO_DURATION_SEC = float(os.environ.get("TENCLIP_MAX_VIDEO_SEC", "300"))

Mode = Literal["eco", "balanced", "quality"]

PRESETS: Dict[Mode, Dict[str, int]] = {
    "eco": {"num_frames": 4, "max_side": 384, "max_new_tokens": 384},
    "balanced": {"num_frames": 6, "max_side": 448, "max_new_tokens": 512},
    "quality": {"num_frames": 8, "max_side": 512, "max_new_tokens": 640},
}

_MODEL = None
_PROCESSOR = None
_TF_KEY: Tuple[str, bool] | None = None

_LF_CHAT = None
_LF_STATE: Tuple[str, Mode, int, int | None] | None = None

COACH_PROMPT = """你是资深网球教练助手。下面是从同一段网球练习或比赛视频中按时间顺序均匀采样的若干关键帧（不是完整视频）。
请根据可见的身体姿态、站位、引拍、击球点、随挥与脚步，尽量回答：
1) 动作整体上是否合理、有哪些明显优点或风险；
2) 若为初学者，给出可操作的改进建议（分条、具体）；
3) 若画面模糊、角度不佳或信息不足，请明确说明局限，不要编造细节。
请用中文回答，语气专业、克制。"""


def _import_llamafactory() -> bool:
    try:
        from llamafactory.chat import ChatModel  # noqa: F401
        return True
    except ImportError:
        return False


def _import_transformers_stack() -> bool:
    try:
        import torch  # noqa: F401
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration  # noqa: F401
        from qwen_vl_utils import process_vision_info  # noqa: F401
        return True
    except ImportError:
        return False


def infer_backend_choice() -> Tuple[bool, str, str]:
    """
    Returns (ok, backend, err_msg).
    backend: llamafactory | transformers
    """
    raw = os.environ.get("TENCLIP_INFER_BACKEND", "auto").strip().lower()
    lf = _import_llamafactory()
    tf = _import_transformers_stack()

    if raw == "llamafactory":
        if lf:
            return True, "llamafactory", ""
        return False, "", "未安装 LLaMA-Factory。请执行：pip install -r requirements-llm-lf.txt"
    if raw == "transformers":
        if tf:
            return True, "transformers", ""
        return (
            False,
            "",
            "未安装 Transformers 视觉栈。请执行：pip install -r requirements-llm.txt",
        )
    if lf:
        return True, "llamafactory", ""
    if tf:
        return True, "transformers", ""
    return (
        False,
        "",
        "未安装推理依赖。至少执行：pip install -r requirements-llm.txt；"
        "若需默认的 LLaMA-Factory 推理再安装：pip install -r requirements-llm-lf.txt",
    )


def vlm_dependency_message() -> str:
    ok, _, err = infer_backend_choice()
    if ok:
        return ""
    return err


def check_vlm_dependencies() -> Tuple[bool, str]:
    ok, _, err = infer_backend_choice()
    return ok, err


def _subclip(clip: Any, start: float, end: float) -> Any:
    if hasattr(clip, "subclipped"):
        return clip.subclipped(start, end)
    return clip.subclip(start, end)


def sample_frames(
    video_path: str,
    max_duration_sec: float,
    num_frames: int,
    max_side: int,
):
    from PIL import Image

    clip = VideoFileClip(video_path)
    try:
        duration = float(clip.duration)
        if duration <= 0:
            raise ValueError("无法读取视频时长")

        if duration > max_duration_sec:
            work = _subclip(clip, 0.0, max_duration_sec)
            clip.close()
            clip = work
            duration = float(clip.duration)

        n = max(1, int(num_frames))
        times = [duration * (i + 1) / (n + 1) for i in range(n)]
        images: List[Any] = []
        for t in times:
            frame = clip.get_frame(t)
            im = Image.fromarray(frame.astype("uint8"), mode="RGB")
            w, h = im.size
            scale = min(max_side / float(w), max_side / float(h), 1.0)
            if scale < 1.0:
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
            images.append(im)
        return images, duration
    finally:
        clip.close()


def _model_source_label(local_dir: str) -> str:
    raw = os.environ.get("TENCLIP_VLM_MODEL", "").strip()
    if raw and os.path.isdir(raw):
        return "本地路径"
    return download_source()


def _get_lf_chat(local_dir: str, mode: Mode):
    global _LF_CHAT, _LF_STATE
    preset = PRESETS[mode]
    max_side = preset["max_side"]
    image_max_pixels = max(32 * 32, max_side * max_side)
    # 弱显卡：eco / balanced 用 4bit；quality 全精度（更吃显存）
    quant: int | None = None if mode == "quality" else 4

    state = (local_dir, mode, image_max_pixels, quant)
    if _LF_CHAT is not None and _LF_STATE == state:
        return _LF_CHAT

    if os.environ.get("TENCLIP_FORCE_CPU", "").strip().lower() in ("1", "true", "yes", "on"):
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    from llamafactory.chat import ChatModel

    args: Dict[str, Any] = {
        "model_name_or_path": local_dir,
        "template": "qwen2_vl",
        "infer_backend": "huggingface",
        "trust_remote_code": True,
        "image_max_pixels": image_max_pixels,
    }
    if quant is not None:
        args["quantization_bit"] = quant

    _LF_CHAT = ChatModel(args)

    _LF_STATE = state
    return _LF_CHAT


def _analyze_llamafactory(
    local_dir: str,
    mode: Mode,
    images: List[Any],
    analyzed_duration: float,
    max_new_tokens: int,
    max_side: int,
) -> str:
    chat = _get_lf_chat(local_dir, mode)
    messages = [{"role": "user", "content": COACH_PROMPT}]
    responses = chat.chat(messages, images=images, max_new_tokens=max_new_tokens)
    reply = responses[0].response_text
    header = (
        f"推理后端: LLaMA-Factory (HuggingFace engine)\n"
        f"权重: {_model_source_label(local_dir)} → `{local_dir}`\n"
        f"模式={mode}，采样 {len(images)} 帧，最长边约 ≤{max_side}px，"
        f"分析时长约 {analyzed_duration:.1f}s（上限 {int(MAX_VIDEO_DURATION_SEC)}s）。\n"
        f"默认远程模型 ID（未指定本地目录时）: {default_remote_model_id()}\n\n---\n\n"
    )
    return header + reply.strip()


def _load_transformers_model(local_dir: str):
    global _MODEL, _PROCESSOR, _TF_KEY

    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2VLForConditionalGeneration

    force_cpu = os.environ.get("TENCLIP_FORCE_CPU", "").strip().lower() in ("1", "true", "yes", "on")
    use_cuda = torch.cuda.is_available() and not force_cpu
    key = (local_dir, force_cpu)
    if _MODEL is not None and _PROCESSOR is not None and _TF_KEY == key:
        return _MODEL, _PROCESSOR

    _PROCESSOR = AutoProcessor.from_pretrained(local_dir, trust_remote_code=True)
    model = None

    if use_cuda:
        try:
            bnb = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
            )
            model = Qwen2VLForConditionalGeneration.from_pretrained(
                local_dir,
                trust_remote_code=True,
                quantization_config=bnb,
                device_map="auto",
            )
            logger.info("Loaded VLM (transformers) 4-bit on GPU.")
        except Exception as e:
            logger.info("4-bit GPU load failed (%s); trying fp16.", e)
            try:
                model = Qwen2VLForConditionalGeneration.from_pretrained(
                    local_dir,
                    trust_remote_code=True,
                    torch_dtype=torch.float16,
                    device_map="auto",
                )
                logger.info("Loaded VLM (transformers) fp16 on GPU.")
            except Exception as e2:
                logger.info("fp16 GPU failed (%s); CPU fp32.", e2)
                use_cuda = False

    if model is None:
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            local_dir,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            device_map=None,
        )
        model = model.to("cpu")
        logger.info("Loaded VLM (transformers) on CPU.")

    _MODEL = model
    _TF_KEY = key
    return _MODEL, _PROCESSOR


def _analyze_transformers(
    local_dir: str,
    mode: Mode,
    images: List[Any],
    analyzed_duration: float,
    max_new_tokens: int,
    max_side: int,
) -> str:
    from qwen_vl_utils import process_vision_info
    import torch

    model, processor = _load_transformers_model(local_dir)

    content: List[Dict[str, Any]] = []
    for im in images:
        content.append({"type": "image", "image": im})
    content.append({"type": "text", "text": COACH_PROMPT})
    mm_messages = [{"role": "user", "content": content}]

    text = processor.apply_chat_template(mm_messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(mm_messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    device = next(model.parameters()).device
    inputs = inputs.to(device)

    header = (
        f"推理后端: Transformers（直连）\n"
        f"权重: {_model_source_label(local_dir)} → `{local_dir}`\n"
        f"模式={mode}，采样 {len(images)} 帧，最长边约 ≤{max_side}px，"
        f"分析时长约 {analyzed_duration:.1f}s（上限 {int(MAX_VIDEO_DURATION_SEC)}s）。\n"
        f"默认远程模型 ID（未指定本地目录时）: {default_remote_model_id()}\n\n---\n\n"
    )

    try:
        with torch.inference_mode():
            out_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
        trimmed = [o[len(i) :] for i, o in zip(inputs.input_ids, out_ids)]
        reply = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    except Exception as e:
        err = str(e).lower()
        if "out of memory" in err or type(e).__name__ in ("OutOfMemoryError",):
            return (
                header
                + "显存不足（CUDA OOM）。建议：选「省显存」、剪短视频，或设置 TENCLIP_FORCE_CPU=1。"
            )
        return header + f"生成失败：{e}"

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return header + reply.strip()


def analyze_tennis_video(video_path: str, mode: Mode = "eco") -> str:
    if not video_path or not os.path.isfile(video_path):
        return "请先上传有效的视频文件。"

    ok, backend, err = infer_backend_choice()
    if not ok:
        return err

    preset = PRESETS.get(mode, PRESETS["eco"])
    num_frames = preset["num_frames"]
    max_side = preset["max_side"]
    max_new_tokens = preset["max_new_tokens"]

    probe = VideoFileClip(video_path)
    try:
        total_dur = float(probe.duration)
    finally:
        probe.close()

    if total_dur > MAX_VIDEO_DURATION_SEC:
        return (
            f"当前视频时长约 {total_dur:.1f} 秒，超过上限 {int(MAX_VIDEO_DURATION_SEC)} 秒（约 5 分钟）。\n"
            "请先使用「视频剪辑」标签截取后再分析。"
        )

    try:
        images, analyzed_duration = sample_frames(
            video_path,
            MAX_VIDEO_DURATION_SEC,
            num_frames=num_frames,
            max_side=max_side,
        )
    except Exception as e:
        return f"抽帧失败：{e}"

    try:
        local_dir = get_local_model_dir()
    except Exception as e:
        return f"模型准备失败（下载或路径解析）：{e}\n若 ModelScope 不可用，可设置 TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface 重试。"

    if backend == "llamafactory":
        try:
            return _analyze_llamafactory(
                local_dir, mode, images, analyzed_duration, max_new_tokens, max_side
            )
        except Exception as e:
            logger.warning("LLaMA-Factory 推理失败，尝试回退 Transformers：%s", e)
            if not _import_transformers_stack():
                return f"LLaMA-Factory 推理失败且无法回退 Transformers：{e}"
            return _analyze_transformers(
                local_dir, mode, images, analyzed_duration, max_new_tokens, max_side
            )

    return _analyze_transformers(
        local_dir, mode, images, analyzed_duration, max_new_tokens, max_side
    )
