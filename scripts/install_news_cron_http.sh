#!/usr/bin/env bash
# 安装 HTTP 新闻抓取 crontab（默认每 2 小时；要求 TenClip API 已在跑）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_BASE="${TENCLIP_NEWS_INGEST_URL:-http://127.0.0.1:7861}"
# 默认每 2 小时；可用 NEWS_CRON_SCHEDULE 覆盖
SCHEDULE="${NEWS_CRON_SCHEDULE:-0 */2 * * *}"
SCRIPT="${ROOT_DIR}/scripts/news_ingest_via_http.sh"
chmod +x "${SCRIPT}"

CRON_LINE="${SCHEDULE} TENCLIP_NEWS_INGEST_URL=${API_BASE} ${SCRIPT} 20 >/dev/null 2>&1"

EXISTING="$(crontab -l 2>/dev/null || true)"
CLEANED="$(echo "${EXISTING}" | grep -Fv "scripts/news_ingest_once.py" | grep -Fv "scripts/news_ingest_via_http.sh" || true)"

{
  echo "${CLEANED}"
  echo "${CRON_LINE}"
} | crontab -

echo "已安装 HTTP 新闻抓取定时任务（默认每 2 小时）："
echo "${CRON_LINE}"
echo "请确认 API 可访问：curl -s ${API_BASE}/api/mobile/health"
echo "立即试跑：TENCLIP_NEWS_INGEST_URL=${API_BASE} ${SCRIPT} 10"
