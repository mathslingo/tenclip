#!/usr/bin/env bash
# 将 Hugging Face 缓存中的 Qwen2-VL-2B 快照复制到项目 model/（解除 symlink，便于自包含）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${HF_SNAPSHOT:-$HOME/.cache/huggingface/hub/models--Qwen--Qwen2-VL-2B-Instruct/snapshots/895c3a49bc3fa70a340399125c650a463535e71c}"
DST="$ROOT/model/Qwen2-VL-2B-Instruct"
if [[ ! -d "$SRC" ]]; then
  echo "未找到快照目录: $SRC"
  echo "请设置 HF_SNAPSHOT=你的/snapshots/xxx 后重试，或先完成 download_vlm_weights.py"
  exit 1
fi
mkdir -p "$DST"
echo "从 $SRC"
echo "到 $DST"
cp -rL "$SRC"/. "$DST"/
du -sh "$DST"
echo "完成。请在 .env 中设置: TENCLIP_VLM_MODEL=$DST"
