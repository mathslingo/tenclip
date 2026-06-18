"""
网球视频抽帧 + 视觉语言模型分析。

- 权重获取：默认 **ModelScope**（`TENCLIP_MODEL_DOWNLOAD_SOURCE=modelscope`），避免 Hugging Face 不可达。
- 推理框架：默认 **LLaMA-Factory** `ChatModel`（`TENCLIP_INFER_BACKEND=auto|llamafactory|transformers`），
  不可用时回退到原生 Transformers + qwen_vl_utils。
"""

from __future__ import annotations

import importlib.util
import logging
import os
from typing import Any, Callable, Dict, List, Literal, Tuple

from moviepy.video.io.VideoFileClip import VideoFileClip

from services.model_resolve import default_remote_model_id, download_source, get_local_model_dir

logger = logging.getLogger(__name__)

MAX_VIDEO_DURATION_SEC = float(os.environ.get("TENCLIP_MAX_VIDEO_SEC", "300"))

Mode = Literal["eco", "balanced", "quality"]

PRESETS: Dict[Mode, Dict[str, int]] = {
    # max_new_tokens：解码上限；过小会在中文长回答中途被截断（表现为句子突然结束）。
    "eco": {"num_frames": 4, "max_side": 384, "max_new_tokens": 1024},
    "balanced": {"num_frames": 6, "max_side": 448, "max_new_tokens": 1536},
    "quality": {"num_frames": 8, "max_side": 512, "max_new_tokens": 2048},
}


def effective_max_new_tokens(mode: Mode) -> int:
    """各 perf 模式的默认 max_new_tokens；可由 `TENCLIP_MAX_NEW_TOKENS` 覆盖（整数，建议 512–4096）。"""
    raw = os.environ.get("TENCLIP_MAX_NEW_TOKENS", "").strip()
    if raw:
        try:
            n = int(raw)
            return max(128, min(n, 8192))
        except ValueError:
            logger.warning("TENCLIP_MAX_NEW_TOKENS 无效，忽略: %r", raw)
    preset = PRESETS.get(mode, PRESETS["eco"])
    return int(preset["max_new_tokens"])


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
    "step_by_step_v2": """你是网球动作分析助手。输入是同一段视频按时间顺序采样的关键帧 F1→F2→...→Fn（非连续视频）。
你的目标是：在不编造细节的前提下，给出“证据驱动 + 限额深度”的分析。

## 总规则（必须遵守）
1) 所有判断先有证据：先列观察证据，再给结论；没有证据就写“未知/不足以判断”。
2) 禁止重复模板句和左右镜像罗列；同类信息必须合并。
3) 不使用第一人称叙事，不写“我在挥拍”；使用客观第三人称。
4) 帧间不可见动作只能写“推测”，且必须带上依据。
5) 任何小节超过限定条数时，自动压缩，不要凑字数。

## 输出采用“双阶段”结构（标题固定）

### 阶段A：证据提取（仅观察，不下结论）
输出一个证据表（最多 8 条）：
| 证据ID | 帧段 | 可见事实（可核对） | 置信度(高/中/低) |
要求：
- 每条必须引用帧段（如 F1~F2、F3）。
- “可见事实”只写画面可核对内容，不解释原因。
- 若多人，先说明分析主体识别依据（占 1 条证据）。

### 阶段B：基于证据的深度分析（所有结论必须引用证据ID）
按以下小节输出：

#### 1) 动作链与关键问题（≤4 条）
- 每条格式：结论 → 证据ID（如 E2,E4）→ 对击球稳定性的影响

#### 2) 机制解释（≤3 条）
- 每条格式：现象 → 可能机制（证据充分/推测）→ 证据ID

#### 3) 优先级（P0/P1/P2，最多 3 项）
- 每项 1-2 句，必须包含对应证据ID

#### 4) 纠正方案（3 天微周期）
- Day1/Day2/Day3 各 1 行：目标 + 2 个练习（组数/时长）+ 1 个自检问题
- 练习必须可在业余条件下执行（半场/墙/影子挥拍）

#### 5) 不确定性与补拍建议（≤4 条）
- 哪些关键判断受限于当前帧
- 下次拍摄建议（机位/距离/帧率）

## 额外格式要求
- 使用 Markdown。
- 全文控制在约 500-900 中文字，优先高信息密度。
- 不得出现未在证据表中出现的新“硬事实”。
""",
    # 参考近年 Video-LLM 工程常见做法：时间对齐、证据绑定到帧序、结构化输出、显式不确定性，降低“时间幻觉”。
    "motion_deep": """你是资深网球动作分析师（非医疗诊断）。输入为**同一段视频按时间顺序均匀采样的关键帧** F1→F2→…→Fn（不是连续视频；相邻帧之间可能存在未观测到的动作变化）。

## 硬性规则（必须遵守）
1) **证据绑定**：凡涉及具体动作判断，尽量用“在 Fi~Fj 可见/不可见”表述；看不清就写**未知**，不要编造关节角度、球速、击球瞬间细节。
2) **时间诚实**：不要声称采样间隔内发生的动作；可写“从 Fi 到 Fj 的姿态变化推断可能发生了…”并标注为**推测**。
3) **主体识别**：若画面多人，先说明分析对象（例如离镜头最近、持拍手清晰者），否则默认分析最像主要练习者的人。
4) **输出语言**：中文；可用 Markdown 标题与小节；避免空泛形容词堆砌。
5) **去冗余（极重要）**：禁止用同一模板句反复排比（例如连续多句「我的左/右…准备挥拍」或「XX弯曲，准备挥拍」）；禁止对左右肢体对称式逐关节机械罗列——**同类信息合并为一条概括**；全篇句式要有变化；任一小节若要点超过 **12 条** 必须停笔并改为**一段不超过 6 句的概括**。
6) **叙述视角**：用第三人称或「可见/画面中」客观描述；**不要**用第一人称扮演运动员讲故事。

## 分析框架（在信息够用的前提下尽量具体；帧少时宁可短、准、合并写）
请按下面结构输出（小节标题保持一致）：

### 1) 任务与输入约束复述
- **仅 2～3 句**：说明你在做「基于稀疏关键帧的网球动作点评」、采样意味着什么、哪些结论做不到。
- **禁止**在本节展开具体动作描写或逐帧叙述（那些放在第 2 节）。

### 2) 逐段时序观察（按 F1→Fn）
- 将帧序列划分为 **2～3 个**时间段（帧很少时只用 **2 段**）；每段 **≤4 条**要点，每条一行、信息不重复。
- 每段写清：站位/躯干与髋肩关系/手臂与拍面大致走向/脚步或重心线索里**最关键的一两点**即可，附带 1 条可核对证据（Fi~Fj）。
- **禁止**逐帧、逐关节、左右镜像式刷屏列举。

### 3) 动作分解与动力链（网球专项）
用 **≤6 条**短要点覆盖下列维度（无证据则写「不足以判断」一条带过，不要硬写）：
准备与读球｜转体与肩髋分离｜引拍与拍面｜击球区（有线索才写）｜随挥与还原。

### 4) 机制层解释（为什么会这样）
**2～4 条**即可，每条一行，格式：现象 → 可能原因（证据充分/推测）→ 对稳定性的影响。

### 5) 风险与优先级（P0/P1/P2）
**最多 4 条**，每条 1～2 句，含可观察线索。

### 6) 训练处方（可执行）
给出 **5 天**即可（每天 20–35 分钟）；每天：**目标 1 句 + 练习 2 条（名称+组数/时长+成功标准）+ 自我检查 1 问**。不要复制粘贴多天相同内容。

### 7) 复盘与下次拍摄建议
- 各 **≤3 条**要点：复盘看什么角度、拍摄机位/距离/帧率建议。

### 8) 不确定性与信息需求
**≤5 条** bullet，说明还需哪些画面信息才能更确定。

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
        ("分步v2(证据驱动)", "step_by_step_v2"),
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


def _spec_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def infer_backend_choice_specs_only() -> Tuple[bool, str, str]:
    """
    仅检查包是否「看起来已安装」，不 import torch/transformers（启动 Gradio 时否则会极慢）。
    真正跑推理前仍由 `infer_backend_choice()` 做完整导入校验。
    """
    raw = os.environ.get("TENCLIP_INFER_BACKEND", "auto").strip().lower()
    lf = _spec_available("llamafactory.chat") or _spec_available("llamafactory")
    tf = (
        _spec_available("torch")
        and _spec_available("transformers")
        and _spec_available("qwen_vl_utils")
    )

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
    ok, _, err = infer_backend_choice_specs_only()
    if ok:
        return ""
    return err


def check_vlm_dependencies() -> Tuple[bool, str]:
    ok, _, err = infer_backend_choice_specs_only()
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
        f"分析时长约 {analyzed_duration:.1f}s（上限 {int(MAX_VIDEO_DURATION_SEC)}s），"
        f"解码 token 上限 max_new_tokens={max_new_tokens}。\n"
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
        f"分析时长约 {analyzed_duration:.1f}s（上限 {int(MAX_VIDEO_DURATION_SEC)}s），"
        f"解码 token 上限 max_new_tokens={max_new_tokens}。\n"
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


def analyze_tennis_video(
    video_path: str,
    mode: Mode = "eco",
    prompt_profile: str | None = None,
    on_progress: Callable[[str, float], None] | None = None,
) -> str:
    def prog(msg: str, frac: float) -> None:
        if on_progress:
            on_progress(msg, frac)

    if not video_path or not os.path.isfile(video_path):
        return "请先上传有效的视频文件。"

    ok, backend, err = infer_backend_choice()
    if not ok:
        return err

    preset = PRESETS.get(mode, PRESETS["eco"])
    num_frames = preset["num_frames"]
    max_side = preset["max_side"]
    max_new_tokens = effective_max_new_tokens(mode)

    prog("读取视频信息…", 0.08)
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

    prog(f"从视频抽帧（约 {min(total_dur, MAX_VIDEO_DURATION_SEC):.0f}s）…", 0.18)
    try:
        images, analyzed_duration = sample_frames(
            video_path,
            MAX_VIDEO_DURATION_SEC,
            num_frames=num_frames,
            max_side=max_side,
        )
    except Exception as e:
        return f"抽帧失败：{e}"

    prog("加载模型权重（首次较慢）…", 0.35)
    try:
        local_dir = get_local_model_dir()
    except Exception as e:
        return f"模型准备失败（下载或路径解析）：{e}\n若 ModelScope 不可用，可设置 TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface 重试。"

    prog("VLM 推理生成指导意见…", 0.55)
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


def infer_vision_chat(
    images: List[Any],
    prompt: str,
    *,
    mode: Mode = "eco",
    max_new_tokens: int | None = None,
    system_prompt: str | None = None,
) -> str:
    """
    通用多图 + 文本 VLM 推理，供 HTTP API 与其它模块调用（不附加网球教练元信息头）。
    """
    if not images:
        raise ValueError("至少需要一张图片")
    if not (prompt or "").strip():
        raise ValueError("prompt 不能为空")

    ok, backend, err = infer_backend_choice()
    if not ok:
        raise RuntimeError(err)

    preset = PRESETS.get(mode, PRESETS["eco"])
    max_new = max_new_tokens if max_new_tokens is not None else effective_max_new_tokens(mode)
    local_dir = get_local_model_dir()

    if backend == "llamafactory":
        chat = _get_lf_chat(local_dir, mode)
        messages: List[Dict[str, str]] = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": prompt.strip()})
        responses = chat.chat(messages, images=images, max_new_tokens=max_new)
        return responses[0].response_text.strip()

    model, processor = _load_transformers_model(local_dir)
    from qwen_vl_utils import process_vision_info
    import torch

    content: List[Dict[str, Any]] = []
    for im in images:
        content.append({"type": "image", "image": im})
    content.append({"type": "text", "text": prompt.strip()})
    mm_messages: List[Dict[str, Any]] = []
    if system_prompt and system_prompt.strip():
        mm_messages.append({"role": "system", "content": system_prompt.strip()})
    mm_messages.append({"role": "user", "content": content})

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

    with torch.inference_mode():
        out_ids = model.generate(**inputs, max_new_tokens=max_new)
    trimmed = [o[len(i) :] for i, o in zip(inputs.input_ids, out_ids)]
    reply = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return reply.strip()


_GUIDANCE_META_SEP = "\n\n---\n\n"


def format_guidance_markdown(raw: str) -> str:
    """
    将 `analyze_tennis_video` 返回的「元信息 + --- + Markdown 正文」整理为更易读的 Markdown，
    供 Gradio `Markdown` 等组件渲染：正文在上，运行参数默认折叠在下方。
    """
    if not raw:
        return ""
    text = raw.strip()
    if _GUIDANCE_META_SEP not in text:
        return text
    meta, body = text.split(_GUIDANCE_META_SEP, 1)
    meta = meta.strip()
    body = body.strip()
    if not body:
        body = "（模型未返回正文）"
    # 避免 meta 内出现 ``` 破坏外层围栏
    safe_meta = meta.replace("```", "``\u200b`")
    return (
        "## 指导意见\n\n"
        f"{body}\n\n"
        "<details><summary><strong>运行环境与参数</strong>（点击展开）</summary>\n\n"
        f"```text\n{safe_meta}\n```\n\n</details>"
    )
