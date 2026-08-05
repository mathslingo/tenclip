#!/usr/bin/env bash
# 安装「每 30 分钟」HTTP 抓取 crontab（要求 TenClip API 已在跑）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_BASE="${TENCLIP_NEWS_INGEST_URL:-http://127.0.0.1:7862}"
# 默认每 30 分钟；可用 NEWS_CRON_SCHEDULE 覆盖
SCHEDULE="${NEWS_CRON_SCHEDULE:-*/30 * * * *}"
SCRIPT="${ROOT_DIR}/scripts/news_ingest_via_http.sh"
chmod +x "${SCRIPT}"

CRON_LINE="${SCHEDULE} TENCLIP_NEWS_INGEST_URL=${API_BASE} ${SCRIPT} 30 >/dev/null 2>&1"

EXISTING="$(crontab -l 2>/dev/null || true)"
CLEANED="$(echo "${EXISTING}" | grep -Fv "scripts/news_ingest_once.py" | grep -Fv "scripts/news_ingest_via_http.sh" || true)"

{
  echo "${CLEANED}"
  echo "${CRON_LINE}"
} | crontab -

echo "已安装 HTTP 新闻抓取定时任务（每 30 分钟）："
echo "${CRON_LINE}"
echo "请确认 API 可访问：curl -s ${API_BASE}/api/mobile/health"
echo "立即试跑：TENCLIP_NEWS_INGEST_URL=${API_BASE} ${SCRIPT} 10"
