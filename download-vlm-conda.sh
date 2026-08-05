#!/usr/bin/env bash
# 在 WSL 中把 Qwen2-VL-2B 权重下载到本机缓存（默认 ModelScope）。
# ModelScope 慢时可改用 HF + 镜像，在运行前 export：
#   export TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface
#   export HF_ENDPOINT=https://hf-mirror.com
# 或走代理：export HTTPS_PROXY=http://127.0.0.1:7890
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINICONDA_ROOT="${MINICONDA_ROOT:-${HOME}/miniconda3}"
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  MINICONDA_ROOT="${HOME}/anaconda3"
fi
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  echo "未找到 conda，请设置 MINICONDA_ROOT"
  exit 1
fi
source "${MINICONDA_ROOT}/etc/profile.d/conda.sh"
conda activate tenclip
cd "$ROOT"
echo "=== 下载 VLM 权重（TENCLIP_MODEL_DOWNLOAD_SOURCE=${TENCLIP_MODEL_DOWNLOAD_SOURCE:-modelscope}）==="
python scripts/download_vlm_weights.py
echo "=== 完成。下一步: bash run-wsl.sh ==="
