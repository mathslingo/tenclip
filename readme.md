# TenClip：本地轻量网球视频理解 Demo

在**有限本机 GPU**上跑通一条完整链路：**视频剪辑** + **网球动作相关的视频理解**（抽帧 + 小参数多模态模型），**模型与推理数据默认都在本地**（权重首次从 ModelScope/HF 拉取后缓存在本机，视频由用户本地上传）。

推理栈与 [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) 对齐：默认用其 `ChatModel`（可回退 Transformers）。后续若要做网球域 SFT，可在同环境用 LLaMA-Factory 训练，再把合并后的**本地目录**指给 `TENCLIP_VLM_MODEL`。

---

## 开发约定（本项目统一采用）


| 项         | 要求                                                                                       |
| --------- | ---------------------------------------------------------------------------------------- |
| 系统        | **WSL2 + Ubuntu**（与 Windows 同机即可）                                                        |
| Python 环境 | **Conda 环境名必须为 `tenclip`**（Miniconda/Anaconda 均可）                                        |
| 本地权重      | 放在 `**model/Qwen2-VL-2B-Instruct/**` 时，`app.py` 会自动设置 `TENCLIP_VLM_MODEL`，推理直接读 `model/` |


首次进入仓库建议在 WSL 里执行（可选）：

```bash
chmod +x run-wsl.sh download-vlm-conda.sh scripts/verify_wsl_env.sh
bash scripts/verify_wsl_env.sh
```

---

## 分阶段路线图（同步维护）

以下为**计划与当前进度**，后续迭代会继续在本文更新勾选状态。

### 阶段 1：环境与本地权重（当前重点）


| 步骤  | 内容                                                                                                         | 状态                    |
| --- | ---------------------------------------------------------------------------------------------------------- | --------------------- |
| 1.1 | WSL2 Ubuntu + `conda activate tenclip` + GPU 可用（`nvidia-smi` / `torch.cuda.is_available()`）                | ⬜ 由你在本机确认             |
| 1.2 | 运行 `bash scripts/verify_wsl_env.sh` 通过                                                                     | ⬜                     |
| 1.3 | **本地下载 VLM 权重**：`python scripts/download_vlm_weights.py`（可 HF + `HF_ENDPOINT=https://hf-mirror.com`）       | ✅ 可已完成（见 `model/`）    |
| 1.4 | （推荐）复制到项目：`bash scripts/copy_vlm_to_model.sh`，`.env` 设置 `TENCLIP_VLM_MODEL=.../model/Qwen2-VL-2B-Instruct` | ⬜ 见 `model/README.md` |
| 1.5 | （可选）`export MODELSCOPE_CACHE=~/modelscope-cache` 把缓存固定到大磁盘                                                 | ⬜                     |


**默认模型**：`Qwen/Qwen2-VL-2B-Instruct`（约 2B，适合 6GB 级显存配合 4bit/少帧）。

### 阶段 2：Demo 闭环（功能已具备，阶段 1 完成后验收）


| 步骤  | 内容                                       | 状态      |
| --- | ---------------------------------------- | ------- |
| 2.1 | `bash run-wsl.sh` 启动 Gradio              | ⬜       |
| 2.2 | 「视频剪辑」：上传 → 按秒裁剪 → 下载                    | ✅ 已实现   |
| 2.3 | 「网球动作分析」：上传 → 省显存模式 → 生成中文指导（基于抽帧，非专业动捕） | ✅ 已实现   |
| 2.4 | 6GB 显存：界面保持 **省显存**，长视频先剪辑再分析            | ✅ 策略已内置 |


### 阶段 3：数据与可选微调（本地数据）


| 步骤  | 内容                                                               | 状态     |
| --- | ---------------------------------------------------------------- | ------ |
| 3.1 | 用剪辑功能准备短片段，自建「视频帧 + 文本标签」数据规范（README 后续可补样例）                     | ⬜      |
| 3.2 | 仓库内已有 `data/` 下 mock 与 `dataset_info.json`，仅供 LLaMA-Factory 实验参考 | ✅ 占位数据 |
| 3.3 | 使用 LLaMA-Factory + 合并权重目录，设置 `TENCLIP_VLM_MODEL` 指向本地目录          | ⬜ 可选   |


### 阶段 4：加固与交付


| 步骤  | 内容                                 | 状态      |
| --- | ---------------------------------- | ------- |
| 4.1 | `test_trim2.py` 等烟雾测试              | ✅       |
| 4.2 | 环境变量与故障排查（OOM、仅 CPU）               | ✅ 见下文表格 |
| 4.3 | （可选）统一 `requirements` 与 WSL 已装版本锁定 | ⬜       |


---

## WSL 快速开始（主路径）

```bash
cd ~/code/tenclip   # 你的克隆路径

# 1）自检（不下载模型）
bash scripts/verify_wsl_env.sh

# 2）下载 VLM 到本机缓存（首次必做，体积大）
bash download-vlm-conda.sh

# 3）启动 Web（Windows 浏览器访问即可）
bash run-wsl.sh
```

浏览器打开：`http://127.0.0.1:7860`  
若要从局域网访问，可在 `.env` 或环境中设置 `GRADIO_SERVER_NAME=0.0.0.0`（见 `env.example`）。

`run-wsl.sh` 默认使用 `~/miniconda3`，若你的 Conda 在别处：

```bash
export MINICONDA_ROOT=/你的路径/miniconda3
bash run-wsl.sh
```

### 下载慢：换 Hugging Face、镜像或代理

ModelScope 若特别慢，可**改走 Hugging Face**，并配合**国内镜像端点**（由 `huggingface_hub` 读取 `HF_ENDPOINT`）：

```bash
export TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com
# 与上面等价、便于写进 .env 的别名：
# export TENCLIP_HF_ENDPOINT=https://hf-mirror.com

python scripts/download_vlm_weights.py
# 或一行指定镜像（不改环境变量）：
# python scripts/download_vlm_weights.py --source huggingface --hf-endpoint https://hf-mirror.com
```

**注意**：推理时也要用同一来源，请保持 `TENCLIP_MODEL_DOWNLOAD_SOURCE` 与下载时一致（或直接把 `TENCLIP_VLM_MODEL` 设为已下载的**本地目录**，则不再请求远程）。

走**系统代理**（Clash、V2 等）时，一般设置即可（ModelScope 与 HF 通常都会走）：

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
```

下载脚本启动时会打印当前**下载源、HF_ENDPOINT、是否检测到代理变量**，便于排查。

---

## 功能与限制

### 剪辑

- 支持：`.mp4`、`.mov`、`.avi`
- 输出：`libx264` + `aac` 的 `.mp4`

### 动作分析（视频理解）

- **时长**：默认只分析前 **300 秒**；更长请先用剪辑截断。
- **方式**：均匀 **抽帧** + **Qwen2-VL-2B** 视觉理解；不是逐帧骨骼识别，结论仅供学习参考。
- **本地**：权重缓存在本机；上传视频不离开你的机器（除非你自己配置云端）。

### 弱 GPU（如 RTX 3060 Laptop 6GB）

- 界面选 **「省显存（弱显卡推荐）」**；后台对 LLaMA-Factory 路径在 eco/balanced 下倾向 **4bit**。
- OOM 时：再剪短、关其它占显存程序，或 `TENCLIP_FORCE_CPU=1`（很慢）。

---

## 环境变量（摘要）

完整说明见 `env.example`。


| 变量                                          | 含义                                             | 默认                          |
| ------------------------------------------- | ---------------------------------------------- | --------------------------- |
| `TENCLIP_VLM_MODEL`                         | 本地模型目录，或远程 ID（用于首次下载）                          | `Qwen/Qwen2-VL-2B-Instruct` |
| `TENCLIP_MODEL_DOWNLOAD_SOURCE`             | `modelscope` / `huggingface`                   | `modelscope`                |
| `HF_ENDPOINT`                               | HF Hub 镜像根 URL，如 `https://hf-mirror.com`       | 未设置（官方 hub）                 |
| `TENCLIP_HF_ENDPOINT`                       | 与 `HF_ENDPOINT` 同义；未设 `HF_ENDPOINT` 时生效        | 未设置                         |
| `HTTP_PROXY` / `HTTPS_PROXY`                | 下载走系统代理                                        | 未设置                         |
| `TENCLIP_INFER_BACKEND`                     | `auto` / `llamafactory` / `transformers`       | `auto`                      |
| `TENCLIP_PROMPT_PROFILE`                    | 推理提示词档位：`default` / `compact` / `step_by_step` | `default`                   |
| `TENCLIP_PROMPT_APPEND`                     | 追加到系统提示词末尾的额外要求（用于快速试验）                        | 未设置                         |
| `MODELSCOPE_CACHE`                          | ModelScope 缓存目录                                | 系统默认                        |
| `TENCLIP_MAX_VIDEO_SEC`                     | 分析时长上限（秒）                                      | `300`                       |
| `TENCLIP_FORCE_CPU`                         | 强制走 CPU                                        | 未设置                         |
| `GRADIO_SERVER_NAME` / `GRADIO_SERVER_PORT` | 监听地址与端口                                        | `127.0.0.1` / `7860`        |


---

## 依赖说明

- **WSL `tenclip` 环境**：以你机器上已安装版本为准（Python 3.12 + torch cu130 等可与仓库 `requirements-*.txt` 略有出入，以能跑通自检为准）。
- **新环境从零创建**：仍可用仓库内 `environment.yml`（面向通用 Conda；WSL 同样适用）：
  ```bash
  conda env create -f environment.yml
  conda env update -f environment.yml --prune
  ```
- 根目录 `requirements.txt` / `requirements-llm.txt` / `requirements-llm-lf.txt` 用于对齐依赖意图；**开发以 WSL `tenclip` 为真源**。

---

## 备选：Windows 批处理

若临时在 Windows 上跑：可使用 `run.bat`、`setup-conda-env.bat`、`download-vlm-conda.bat` 等。**不作为本项目推荐开发方式。**

---

## 使用说明

1. **视频剪辑**：上传 → 起止秒数 → 下载。
2. **网球动作分析**：上传 → 显存模式 → **开始分析**。

可选：复制 `env.example` 为 `.env`（需 `python-dotenv`，已在 `requirements.txt`）。

---

## Qwen2-VL-2B 优化方案（Prompt / SFT / DPO）

基于LLaMA-Factory 工作流，把优化拆成三层：**先 Prompt 微调（零训练成本）→ 再 SFT（监督学习）→ 最后 DPO（偏好对齐）**。

### 1) Prompt 微调（最快，先做）

适用场景：你想先快速改变输出风格、结构化程度和保守性，不改模型权重。  
已实现能力（代码已接入）：

- `services/vlm_tennis.py` 支持多档提示词 profile：
  - `default`：当前通用教练风格
  - `compact`：短答 + 清单
  - `step_by_step`：按“观察-机制-纠正步骤-拍摄建议”结构输出
- 可通过环境变量切换：

```bash
export TENCLIP_PROMPT_PROFILE=step_by_step
export TENCLIP_PROMPT_APPEND="优先指出1个最关键风险，并给出一周训练计划。"
bash run-wsl.sh
```

建议做法：

1. 在相同视频集上做 A/B（`default` vs `compact` vs `step_by_step`）
2. 用固定评估表（可执行性、清晰度、幻觉率、长度）打分
3. 把最优 profile 作为 SFT 数据标注风格

### 2) SFT（监督微调）

目标：把“好回答风格”固化到模型参数里，提升稳定性与一致性。  
已补配置（LLaMA-Factory）：

- `configs/train/qwen2_vl_2b_qlora_sft.yaml`
- `data/dataset_info.json` 新增 `mock_tennis_qwen2_vl_sft_10k`

运行示例：

```bash
conda activate tenclip
llamafactory-cli train configs/train/qwen2_vl_2b_qlora_sft.yaml
```

当前仓库提供的是文本 mock 数据（用于流程打通）。生产建议把样本升级为“**视频帧/图像 + 教练答复**”的多模态 SFT 数据，并保持 `template: qwen2_vl`。

### 3) DPO（偏好优化）

目标：在已有 SFT 基础上，把“更优回答 > 较差回答”的偏好进一步对齐。  
已补配置（LLaMA-Factory）：

- `configs/train/qwen2_vl_2b_lora_dpo.yaml`
- `data/dataset_info.json` 新增 `mock_tennis_qwen2_vl_dpo_10k`

运行示例：

```bash
conda activate tenclip
llamafactory-cli train configs/train/qwen2_vl_2b_lora_dpo.yaml
```

推荐流程：

1. 先跑 SFT 得到 adapter（`saves/qwen2_vl_2b/lora/sft`）
2. 用线上/离线评测选出 bad case，构造 chosen/rejected 对
3. 再跑 DPO，观察“建议可执行性”和“错误建议率”变化

### 数据与工程建议（落地优先级）

- **优先级 A：Prompt 评测闭环**（1-2 天就能看到收益）
- **优先级 B：SFT 数据升级到多模态**（帧采样策略与前端分析一致）
- **优先级 C：DPO 难例集**（重点覆盖逆光、远景、遮挡、低帧率）
- 每轮训练都保留评测切分，避免只看训练损失

---

## 本地测试

```bash
conda activate tenclip
python test_trim2.py
```

---

## 项目结构（节选）

```text
tenclip/
├─ app.py
├─ run-wsl.sh              # WSL 主启动（conda tenclip）
├─ download-vlm-conda.sh   # WSL 下载 VLM 权重到本地缓存
├─ run.bat                 # Windows 备选
├─ env.example
├─ environment.yml
├─ requirements*.txt
├─ configs/                # LLaMA-Factory 等实验配置
├─ data/                   # 数据集占位与 dataset_info
├─ model/
│   └─ README.md          # 权重放此目录（已 gitignore，见文内说明）
├─ scripts/
│   ├─ download_vlm_weights.py
│   ├─ copy_vlm_to_model.sh
│   ├─ verify_wsl_env.sh
│   └─ ...
├─ services/
│   ├─ model_resolve.py
│   └─ vlm_tennis.py
└─ test_*.py
```

---

## GitHub

示例：`https://github.com/mathslingo/tenclip`

---

## 附录 A：可选文本模型（DeepSeek 7B + LLaMA-Factory）

与**网球视频主线独立**：仓库内另有 DeepSeek 蒸馏 7B 的下载脚本与推理 YAML，供本地文本/对话实验。网球场 **VLM 默认仍为 Qwen2-VL-2B**。

- 下载：`scripts/download_llm_weights.py`，`download-deepseek-conda.bat`（Windows）
- 配置：`configs/inference/deepseek_r1_7b.yaml`
- 6GB 显存上 7B 建议量化；详见原脚本注释

在 WSL 中若需对等流程，可自行：

```bash
conda activate tenclip
python scripts/download_llm_weights.py
# 再按 configs 使用 llamafactory-cli chat ...
```

（后续若统一 WSL 脚本，可在阶段 4 补 `download-deepseek-wsl.sh`。）