#!/usr/bin/env bash
set -euo pipefail

EXISTING="$(crontab -l 2>/dev/null || true)"
if [[ -z "${EXISTING}" ]]; then
  echo "当前没有 crontab，无需卸载。"
  exit 0
fi

FILTERED="$(echo "${EXISTING}" | grep -Fv "scripts/news_ingest_once.py" || true)"

if [[ -z "${FILTERED}" ]]; then
  crontab -r
  echo "已移除新闻抓取任务；crontab 当前为空。"
else
  echo "${FILTERED}" | crontab -
  echo "已移除新闻抓取任务，其它 crontab 保持不变。"
fi
