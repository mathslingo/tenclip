#!/usr/bin/env bash
# 启动本地 VLM FastAPI 服务（默认 127.0.0.1:7862，与主 app 7861 错开）
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname "$0")" && pwd)"
cd -- "$SCRIPT_DIR/.." || exit 1

HOST="${TENCLIP_VLM_API_HOST:-127.0.0.1}"
PORT="${TENCLIP_VLM_API_PORT:-7862}"

echo "TenClip VLM API → http://${HOST}:${PORT}  (docs: /docs)"
exec python3 -m uvicorn subprojects.vlm_api.app:app --host "$HOST" --port "$PORT"
