# TenClip：网球视频剪辑与动作分析

最小可用的网球相关视频工具：

1. **视频剪辑**：`Gradio + MoviePy`，按秒裁剪并下载。
2. **网球动作分析（大模型）**：对上传视频**均匀抽帧**，调用 **Qwen2-VL-2B-Instruct**（约 2B，满足「3B 以内」）做视觉理解，输出动作是否大致合理、以及给初学者的改进建议。

> **LLaMA-Factory**：本仓库**默认用其 `ChatModel` 做推理**（`TENCLIP_INFER_BACKEND=auto`），与官方训练/微调工作流一致。你也可以用 LLaMA-Factory 在网球数据上做 SFT，合并导出后将 `TENCLIP_VLM_MODEL` 设为**本地合并目录**即可在本应用中分析。

## 功能与限制

### 剪辑

- 支持：`.mp4`、`.mov`、`.avi`
- 输出：`libx264` + `aac` 的 `.mp4`

### 动作分析

- **时长上限**：默认只处理前 **300 秒（约 5 分钟）**；超出请先使用「视频剪辑」截取。
- **不是逐帧专业动作捕捉**：模型看到的是**少量静态关键帧**，结论仅供学习参考，不能替代教练或生物力学评估。
- **权重获取**：默认走 **ModelScope**（国内更稳）；也可切换为 Hugging Face（见环境变量）。体积较大，建议先运行 `download-vlm-conda.bat` 预下载。

## 显卡与性能（弱显卡优先）

界面默认 **「省显存（弱显卡推荐）」**，后台策略包括：

- 更少采样帧、更低分辨率（减少显存与算力）
- 在 **NVIDIA GPU** 上优先尝试 **4-bit 量化**（显著省显存）；失败则退回 **fp16 GPU**；再失败则 **CPU fp32**（很慢但最稳）

若仍显存不足（OOM）：

1. 继续使用「省显存」，并把视频剪到更短再分析。
2. 关闭其他占用显存的程序。
3. 启动前设置环境变量 `TENCLIP_FORCE_CPU=1` 强制走 CPU（速度慢，但不占 GPU 显存）。

可选环境变量：


| 变量                              | 含义                                         | 默认                          |
| ------------------------------- | ------------------------------------------ | --------------------------- |
| `TENCLIP_MAX_VIDEO_SEC`         | 分析时长上限（秒）                                  | `300`                       |
| `TENCLIP_VLM_MODEL`             | **本地目录**（若已下载）或 **远程模型 ID**（ModelScope/HF） | `Qwen/Qwen2-VL-2B-Instruct` |
| `TENCLIP_MODEL_DOWNLOAD_SOURCE` | 远程拉取源：`modelscope` / `huggingface`         | `modelscope`                |
| `TENCLIP_INFER_BACKEND`         | `auto` / `llamafactory` / `transformers`   | `auto`（优先 LLaMA-Factory）    |
| `MODELSCOPE_CACHE`              | ModelScope 缓存目录（可选）                        | 系统默认                        |
| `TENCLIP_FORCE_CPU`             | `1` / `true` 时尽量走 CPU                      | 未设置                         |


## 环境要求

- Python **3.10+**
- **推荐（本仓库）**：用 **Conda** 管理环境（见下文 `environment.yml`）
- **剪辑**：`requirements.txt`
- **分析**：`requirements-llm.txt`（torch、transformers、**modelscope** 等）+ `requirements-llm-lf.txt`（**llamafactory**）

## 安装与启动

根目录提供 `**run.bat`**：若存在 `%CONDA_ROOT%\Scripts\conda.exe`（默认 `C:\Users\baozi\anaconda3`），则 `conda run -n tenclip python app.py`；否则用当前 `python`。可选：复制 `**env.example`** 为 `.env` 配置端口与 `TENCLIP_*` 变量（需已安装 `python-dotenv`，已写在 `requirements.txt`）。

### 方式 A：Conda（推荐，含 ffmpeg + ModelScope + LLaMA-Factory）

**Anaconda 路径**：批处理默认 `CONDA_ROOT=C:\Users\baozi\anaconda3`。若你的安装路径不同，请先：

```bat
set CONDA_ROOT=D:\你的\conda\根目录
```

再运行 `setup-conda-env.bat` / `start-conda-llm.bat`。

1. **创建/更新环境**（`environment.yml` 会安装 `requirements.txt`、`requirements-llm.txt`、`requirements-llm-lf.txt`）：

```bash
conda env create -f environment.yml
conda env update -f environment.yml --prune
```

Windows 可双击 `**setup-conda-env.bat**`（内部使用 `%CONDA_ROOT%\Scripts\conda.exe`）。

1. **（推荐）预下载 VLM 权重**：默认 **ModelScope**，避免 HF 不可达。

```bash
conda activate tenclip
python scripts/download_vlm_weights.py
# 或显式指定源:
python scripts/download_vlm_weights.py --source modelscope --repo Qwen/Qwen2-VL-2B-Instruct
```

或双击 `**download-vlm-conda.bat**`。

若必须用 Hugging Face：`set TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface` 后再运行上述脚本。

1. **启动 Web**：

```bash
conda activate tenclip
python app.py
```

或 `**start-conda-llm.bat**`（等价 `conda run -n tenclip python app.py`）。

浏览器打开：`http://127.0.0.1:7860`

#### NVIDIA GPU（可选）

`environment.yml` 里通过 pip 安装的 PyTorch 多为 **CPU 版**或通用轮子。若需要 **CUDA 版**，在环境创建完成后执行（按你的 CUDA 版本调整 `cu124` 等，参见 [PyTorch 官网](https://pytorch.org/get-started/locally/)）：

```bash
conda activate tenclip
pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### 方式 B：venv + pip（轻量/无 Conda 时）

**仅剪辑**：双击 `start.bat`，或：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**剪辑 + 大模型**：双击 `start-with-llm.bat`，或：

```bash
pip install -r requirements.txt -r requirements-llm.txt -r requirements-llm-lf.txt
python scripts/download_vlm_weights.py   # 可选，默认 ModelScope
python app.py
```

## 使用说明

1. **视频剪辑**：上传视频，填写开始/结束秒数，下载片段。
2. **网球动作分析**：上传视频，选择显存模式，点击「开始分析」查看 Markdown 报告。

## 本地测试脚本

- `test_trim.py` / `test_trim2.py`：剪辑逻辑烟雾测试
- `test_file_type.py`、`test_moviepy.py`：环境检查

## 项目结构

```text
tenclip/
├─ app.py
├─ run.bat
├─ env.example
├─ environment.yml
├─ setup-conda-env.bat
├─ start-conda-llm.bat
├─ download-vlm-conda.bat
├─ start.bat
├─ start-with-llm.bat
├─ requirements.txt
├─ requirements-llm.txt
├─ requirements-llm-lf.txt
├─ readme.md
├─ scripts/
│   └─ download_vlm_weights.py
├─ services/
│   ├─ __init__.py
│   ├─ model_resolve.py
│   └─ vlm_tennis.py
├─ test_*.py
└─ old_version/
   └─ app_v1.py
```

## GitHub

仓库示例：`https://github.com/mathslingo/tenclip`（若你 fork 后地址不同，以你的远程为准。）

## DeepSeek 7B with LLaMA-Factory

This repo now includes a separate local text-model path for LLaMA-Factory:

- Default model: `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`
- Download script: `scripts/download_llm_weights.py`
- Conda helper: `download-deepseek-conda.bat`
- Chat launcher: `start-llamafactory-deepseek-chat.bat`
- Inference config: `configs/inference/deepseek_r1_7b.yaml`

Recommended flow:

```bat
setup-conda-env.bat
download-deepseek-conda.bat
start-llamafactory-deepseek-chat.bat
```

Useful environment variables:

- `TENCLIP_LLM_MODEL`: remote model id or local model directory
- `TENCLIP_LLM_MODEL_DOWNLOAD_SOURCE`: `huggingface` or `modelscope`
- `TENCLIP_LLM_CACHE_DIR`: optional cache directory
- `USE_MODELSCOPE_HUB=1`: recommended when launching LLaMA-Factory with a ModelScope model id

Hardware note:

- `DeepSeek-R1-Distill-Qwen-7B` is feasible on this project as a local text model.
- On a `RTX 3060 Laptop 6GB`, practical inference usually means quantized loading such as 4-bit.
- Full-precision 7B inference is generally not recommended on this machine.

