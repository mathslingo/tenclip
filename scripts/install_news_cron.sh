#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MINICONDA_ROOT="${MINICONDA_ROOT:-${HOME}/miniconda3}"
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  MINICONDA_ROOT="${HOME}/anaconda3"
fi

if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  echo "未找到 conda.sh，请设置 MINICONDA_ROOT 后重试。"
  exit 1
fi

source "${MINICONDA_ROOT}/etc/profile.d/conda.sh"
conda activate tenclip

LOG_DIR="${ROOT_DIR}/data/logs"
mkdir -p "${LOG_DIR}"
RUN_CMD="cd ${ROOT_DIR} && ${MINICONDA_ROOT}/envs/tenclip/bin/python ${ROOT_DIR}/scripts/news_ingest_once.py --limit-per-source 30 >> ${LOG_DIR}/news_ingest.log 2>&1"
CRON_LINE="0 0,6,12,18 * * * ${RUN_CMD}"

EXISTING="$(crontab -l 2>/dev/null || true)"
if echo "${EXISTING}" | grep -Fq "scripts/news_ingest_once.py"; then
  CLEANED="$(echo "${EXISTING}" | grep -Fv "scripts/news_ingest_once.py" || true)"
else
  CLEANED="${EXISTING}"
fi

{
  echo "${CLEANED}"
  echo "${CRON_LINE}"
} | crontab -

echo "已安装新闻抓取定时任务："
echo "${CRON_LINE}"
echo "日志文件：${LOG_DIR}/news_ingest.log"
