#!/usr/bin/env bash
# 安装「每 30 分钟」新闻抓取 crontab（调用 conda 环境中的 news_ingest_once.py）
# 含 Live Tennis CN / ATP / WTA / BBC 等 config/news_sources.json 已启用源 → data/news_feed.db
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MINICONDA_ROOT="${MINICONDA_ROOT:-${HOME}/miniconda3}"
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  MINICONDA_ROOT="${HOME}/anaconda3"
fi

if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  echo "未找到 conda.sh，请设置 MINICONDA_ROOT 后重试；或改用 scripts/install_news_cron_http.sh"
  exit 1
fi

PY="${MINICONDA_ROOT}/envs/tenclip/bin/python"
if [[ ! -x "${PY}" ]]; then
  echo "未找到 ${PY}，请确认 conda 环境 tenclip 已创建。"
  exit 1
fi

LOG_DIR="${ROOT_DIR}/data/logs"
mkdir -p "${LOG_DIR}"

# 默认每 30 分钟；可用 NEWS_CRON_SCHEDULE 覆盖，例如 "0 * * * *" 每小时整点
SCHEDULE="${NEWS_CRON_SCHEDULE:-*/30 * * * *}"
RUN_CMD="cd ${ROOT_DIR} && ${PY} ${ROOT_DIR}/scripts/news_ingest_once.py --limit-per-source 30 >> ${LOG_DIR}/news_ingest.log 2>&1"
CRON_LINE="${SCHEDULE} ${RUN_CMD}"

EXISTING="$(crontab -l 2>/dev/null || true)"
if echo "${EXISTING}" | grep -Fq "scripts/news_ingest_once.py"; then
  CLEANED="$(echo "${EXISTING}" | grep -Fv "scripts/news_ingest_once.py" || true)"
else
  CLEANED="${EXISTING}"
fi
# 同时清掉旧的 HTTP 抓取行，避免重复
if echo "${CLEANED}" | grep -Fq "scripts/news_ingest_via_http.sh"; then
  CLEANED="$(echo "${CLEANED}" | grep -Fv "scripts/news_ingest_via_http.sh" || true)"
fi

{
  echo "${CLEANED}"
  echo "${CRON_LINE}"
} | crontab -

echo "已安装新闻抓取定时任务（每 30 分钟）："
echo "${CRON_LINE}"
echo "日志：${LOG_DIR}/news_ingest.log"
echo "查看：crontab -l | grep news_ingest"
echo "卸载：bash ${ROOT_DIR}/scripts/uninstall_news_cron.sh"
echo "立即试跑：${PY} ${ROOT_DIR}/scripts/news_ingest_once.py --limit-per-source 10"
