# 本地 VLM 权重（不提交到 Git）

本目录用于存放 **Qwen2-VL-2B-Instruct** 等模型的**实体文件**（约 4GB+），由本机复制或下载得到。

## 当前布局（示例）

- `Qwen2-VL-2B-Instruct/`：从 Hugging Face 缓存快照复制而来的完整推理目录（`config.json`、`model*.safetensors` 等）。

## 配置推理使用项目内模型

**默认行为（推荐）**：若存在本目录下的 `Qwen2-VL-2B-Instruct/`，`app.py` 与 `run-wsl.sh` 会**自动**设置 `TENCLIP_VLM_MODEL` 指向该路径，一般**不必**再写 `.env` 或 `export`。

需要覆盖时（例如临时改用远程 ID）再在环境或 `.env` 里设置 `TENCLIP_VLM_MODEL`。

设置后**无需再访问 ModelScope/HF**，`get_local_model_dir()` 会直接使用该目录。

## 如何从缓存再复制一份

```bash
bash scripts/copy_vlm_to_model.sh
```

若快照 commit 与默认不同：

```bash
export HF_SNAPSHOT=~/.cache/huggingface/hub/models--Qwen--Qwen2-VL-2B-Instruct/snapshots/<你的hash>
bash scripts/copy_vlm_to_model.sh
```
