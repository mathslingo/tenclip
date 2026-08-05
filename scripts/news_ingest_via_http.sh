#!/usr/bin/env bash
# 通过 HTTP 调用本机已启动的 TenClip API 做抓取（适合 systemd 常驻服务 + crontab）
# 不依赖 cron 里激活 conda。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_BASE="${TENCLIP_NEWS_INGEST_URL:-http://127.0.0.1:7862}"
# 本地 run-wsl.sh 默认 7861；生产 uchanceai 常见 7862
LIMIT="${1:-30}"
LOG_DIR="${ROOT_DIR}/data/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/news_ingest_http.log"

TS="$(date -Iseconds)"
RESP="$(curl -sS -m 300 -X POST "${API_BASE}/api/news/ingest?limit_per_source=${LIMIT}" || true)"
echo "${TS} ${RESP}" >> "${LOG_FILE}"
echo "${RESP}"
