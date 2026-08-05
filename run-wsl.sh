#!/usr/bin/env bash
# 本项目默认开发方式：在 WSL2 Ubuntu 中激活 conda 环境 tenclip 后启动 Gradio。
# 用法：在仓库根目录执行  bash run-wsl.sh
# 可选：export MINICONDA_ROOT=/path/to/miniconda3  （默认 ~/miniconda3，其次 ~/anaconda3）

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINICONDA_ROOT="${MINICONDA_ROOT:-${HOME}/miniconda3}"
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  MINICONDA_ROOT="${HOME}/anaconda3"
fi
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  echo "未找到 conda.sh：${MINICONDA_ROOT}/etc/profile.d/conda.sh"
  echo "请设置 MINICONDA_ROOT 指向你的 Miniconda/Anaconda 根目录。"
  exit 1
fi
# shellcheck source=/dev/null
source "${MINICONDA_ROOT}/etc/profile.d/conda.sh"
conda activate tenclip
cd "$ROOT"
# 与 app.py 一致：存在 model/Qwen2-VL-2B-Instruct 时默认读项目内权重（可被已有环境变量 / .env 覆盖）
if [[ -z "${TENCLIP_VLM_MODEL:-}" && -d "$ROOT/model/Qwen2-VL-2B-Instruct" ]]; then
  export TENCLIP_VLM_MODEL="$ROOT/model/Qwen2-VL-2B-Instruct"
fi
exec python app.py
