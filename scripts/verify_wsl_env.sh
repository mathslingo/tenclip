#!/usr/bin/env bash
# 阶段 1 自检：WSL + conda tenclip + CUDA + 关键包（不下载模型）。
set -euo pipefail
MINICONDA_ROOT="${MINICONDA_ROOT:-${HOME}/miniconda3}"
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  MINICONDA_ROOT="${HOME}/anaconda3"
fi
source "${MINICONDA_ROOT}/etc/profile.d/conda.sh"
conda activate tenclip
echo "=== TenClip WSL 环境自检 ==="
echo "Python: $(python -V)"
python - <<'PY'
import shutil
print("ffmpeg:", shutil.which("ffmpeg") or "(未在 PATH 中，建议: sudo apt install -y ffmpeg)")
try:
    import torch
    print("torch:", torch.__version__, "cuda_available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("cuda device:", torch.cuda.get_device_name(0))
except Exception as e:
    print("torch:", e)
for m in ("gradio", "modelscope", "transformers", "moviepy"):
    try:
        __import__(m)
        print(m + ": OK")
    except Exception as e:
        print(m + ": FAIL", e)
try:
    from llamafactory.chat import ChatModel  # noqa: F401
    print("llamafactory: OK")
except Exception as e:
    print("llamafactory: FAIL", e)
PY
echo "=== 完成。若 CUDA 为 False，请检查 WSL2 与 NVIDIA 驱动。 ==="
