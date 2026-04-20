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

PROMPT_PROFILES: Dict[str, str] = {
    "default": """你是资深网球教练助手。下面是从同一段网球练习或比赛视频中按时间顺序均匀采样的若干关键帧（不是完整视频）。
请根据可见的身体姿态、站位、引拍、击球点、随挥与脚步，尽量回答：
1) 动作整体上是否合理、有哪些明显优点或风险；
2) 若为初学者，给出可操作的改进建议（分条、具体）；
3) 若画面模糊、角度不佳或信息不足，请明确说明局限，不要编造细节。
请用中文回答，语气专业、克制。""",
    "compact": """你是网球动作分析助手，请基于关键帧直接给结论。
输出格式固定为三段：
【动作判断】1-2 句；
【问题优先级】最多 3 条；
【下次训练清单】最多 5 条，每条一句。
若信息不足必须明确指出，不要编造。""",
    "step_by_step": """你是网球教练。请基于动作关键帧做结构化分析，输出以下小节：
1. 对视频中运动员的一系列动作进行描述，按时间线索；
2. 分别从正手、反手、转体、脚步、动力链（如有）等方面进行点评；
3. 深入分析可能的问题机制（不超过 3 条） 例如：转体不充分、脚步启动过晚等等；
4. 进一步给出可执行纠正步骤；
5. 下一次拍摄建议（机位/距离/帧率）。
请用中文，采用markdown格式。""",
    # 参考近年 Video-LLM 工程常见做法：时间对齐、证据绑定到帧序、结构化输出、显式不确定性，降低“时间幻觉”。
    "motion_deep": """你是资深网球动作分析师（非医疗诊断）。输入为**同一段视频按时间顺序均匀采样的关键帧** F1→F2→…→Fn（不是连续视频；相邻帧之间可能存在未观测到的动作变化）。

## 硬性规则（必须遵守）
1) **证据绑定**：凡涉及具体动作判断，尽量用“在 Fi~Fj 可见/不可见”表述；看不清就写**未知**，不要编造关节角度、球速、击球瞬间细节。
2) **时间诚实**：不要声称采样间隔内发生的动作；可写“从 Fi 到 Fj 的姿态变化推断可能发生了…”并标注为**推测**。
3) **主体识别**：若画面多人，先说明分析对象（例如离镜头最近、持拍手清晰者），否则默认分析最像主要练习者的人。
4) **输出语言**：中文；可用 Markdown 标题与小节；避免空泛形容词堆砌。

## 分析框架（尽量全面、相对深入）
请按下面结构输出（小节标题保持一致）：

### 1) 任务与输入约束复述
- 用 2-4 句说明：你在做什么、关键帧采样意味着什么、哪些结论做不到。

### 2) 逐段时序观察（按 F1→Fn）
- 将帧序列划分为 2-4 个“时间段”（例如早期准备/引拍-挥拍过渡/随挥-还原），每段用要点描述**可见的身体部位与空间关系**（站位、躯干朝向、肩髋分离、手臂轨迹、拍面大致指向、重心、脚步类型如分腿垫步/交叉步等）。
- 每段至少给出 1 条“**可核对的视觉证据**”（你看到了什么）。

### 3) 动作分解与动力链（网球专项）
从以下维度做点评（没有足够证据就写“不足以判断”）：
- **准备与读球**：分腿垫步/启动时机、预判与站位是否合理
- **转体与肩髋分离**：是否形成有效“线圈/链条”
- **引拍与拍面管理**：引拍幅度、拍面稳定性、是否存在“甩臂”代偿
- **击球区与接触点**：是否偏前/偏侧/偏高（仅在有线索时）
- **随挥与减速**：随挥是否完整、是否有助于控球与肩部负荷
- **还原与衔接**：回位路线、下一拍准备

### 4) 机制层解释（为什么会这样）
给出 2-5 条“**可能机制**”，每条格式为：
- 现象 → 可能原因（标注：证据充分 / 推测）→ 对回合稳定性的影响

### 5) 风险与优先级（P0/P1/P2）
- 列出最多 5 个风险点，按 P0（最优先）排序；每条说明**为什么是 P0** 与**可观察线索**。

### 6) 训练处方（7 天可执行）
给出 **7 天** 计划（每天 20-40 分钟即可），每天包含：
- 目标（1 句）
- 2-3 个具体练习（名称 + 组数/时长 + 成功标准）
- 自我检查问题（2 个）
要求：练习必须能在常见业余条件下完成（半场/墙/影子挥拍均可）。

### 7) 复盘与下次拍摄建议
- **复盘**：建议用手机录什么角度、回看时重点看哪 3 个时间点/身体部位
- **拍摄**：机位、距离、帧率/快门建议（避免只给空话）

### 8) 不确定性与信息需求
列出你希望再补充哪些信息才能更确定（例如：更侧面机位、更高帧率、全身入镜、连续慢动作等）。

开始分析。""",
}


def get_prompt_profile() -> str:
    raw = os.environ.get("TENCLIP_PROMPT_PROFILE", "default").strip().lower()
    if raw in PROMPT_PROFILES:
        return raw
    return "default"


def resolve_prompt_profile(override: str | None) -> str:
    """优先使用请求/界面传入的 profile；否则回退环境变量 `TENCLIP_PROMPT_PROFILE`。"""
    key = (override or "").strip().lower()
    if key in PROMPT_PROFILES:
        return key
    return get_prompt_profile()


def get_coach_prompt(override: str | None = None) -> tuple[str, str]:
    profile = resolve_prompt_profile(override)
    base = PROMPT_PROFILES[profile]
    extra = os.environ.get("TENCLIP_PROMPT_APPEND", "").strip()
    if extra:
        return base + "\n\n额外要求：\n" + extra, profile
    return base, profile


def prompt_profile_radio_choices() -> list[tuple[str, str]]:
    """(界面标签, profile key)，供 Gradio Radio 使用。"""
    return [
        ("标准", "default"),
        ("精简", "compact"),
        ("分步", "step_by_step"),
        ("深度", "motion_deep"),
    ]


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
    prompt_profile_override: str | None = None,
) -> str:
    chat = _get_lf_chat(local_dir, mode)
    prompt, prompt_profile = get_coach_prompt(prompt_profile_override)
    messages = [{"role": "user", "content": prompt}]
    responses = chat.chat(messages, images=images, max_new_tokens=max_new_tokens)
    reply = responses[0].response_text
    header = (
        f"推理后端: LLaMA-Factory (HuggingFace engine)\n"
        f"权重: {_model_source_label(local_dir)} → `{local_dir}`\n"
        f"Prompt profile: {prompt_profile}\n"
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
    prompt_profile_override: str | None = None,
) -> str:
    from qwen_vl_utils import process_vision_info
    import torch

    model, processor = _load_transformers_model(local_dir)

    prompt, prompt_profile = get_coach_prompt(prompt_profile_override)
    content: List[Dict[str, Any]] = []
    for im in images:
        content.append({"type": "image", "image": im})
    content.append({"type": "text", "text": prompt})
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
        f"Prompt profile: {prompt_profile}\n"
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


def analyze_tennis_video(video_path: str, mode: Mode = "eco", prompt_profile: str | None = None) -> str:
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
                local_dir,
                mode,
                images,
                analyzed_duration,
                max_new_tokens,
                max_side,
                prompt_profile_override=prompt_profile,
            )
        except Exception as e:
            logger.warning("LLaMA-Factory 推理失败，尝试回退 Transformers：%s", e)
            if not _import_transformers_stack():
                return f"LLaMA-Factory 推理失败且无法回退 Transformers：{e}"
            return _analyze_transformers(
                local_dir,
                mode,
                images,
                analyzed_duration,
                max_new_tokens,
                max_side,
                prompt_profile_override=prompt_profile,
            )

    return _analyze_transformers(
        local_dir,
        mode,
        images,
        analyzed_duration,
        max_new_tokens,
        max_side,
        prompt_profile_override=prompt_profile,
    )
