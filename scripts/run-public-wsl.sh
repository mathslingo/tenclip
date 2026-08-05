#!/usr/bin/env bash
# 一键启动：本地服务 + localhost.run 公网隧道
# 用法：
#   bash scripts/run-public-wsl.sh
# 可选：
#   PUBLIC_PORT=7861 bash scripts/run-public-wsl.sh
#   MINICONDA_ROOT=/home/you/miniconda3 bash scripts/run-public-wsl.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT}/data/logs"
mkdir -p "${LOG_DIR}"

MINICONDA_ROOT="${MINICONDA_ROOT:-${HOME}/miniconda3}"
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  MINICONDA_ROOT="${HOME}/anaconda3"
fi
if [[ ! -f "${MINICONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
  echo "未找到 conda.sh：${MINICONDA_ROOT}/etc/profile.d/conda.sh"
  echo "请设置 MINICONDA_ROOT 指向你的 Miniconda/Anaconda 根目录。"
  exit 1
fi

PORT="${PUBLIC_PORT:-${GRADIO_SERVER_PORT:-7861}}"
APP_LOG="${LOG_DIR}/app_public.log"
TUNNEL_LOG="${LOG_DIR}/public_tunnel.log"
TUNNEL_RESTART_DELAY_SEC="${TUNNEL_RESTART_DELAY_SEC:-3}"
MAX_URL_WAIT_SEC="${MAX_URL_WAIT_SEC:-40}"
LHR_SSH_KEY="${LHR_SSH_KEY:-${HOME}/.ssh/id_ed25519}"

cleanup() {
  set +e
  if [[ -n "${TUNNEL_PID:-}" ]] && kill -0 "${TUNNEL_PID}" 2>/dev/null; then
    kill "${TUNNEL_PID}" 2>/dev/null || true
  fi
  if [[ -n "${APP_PID:-}" ]] && kill -0 "${APP_PID}" 2>/dev/null; then
    kill "${APP_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

start_tunnel() {
  # 新会话清空旧日志，便于解析新的公网 URL。
  : > "${TUNNEL_LOG}"
  ssh \
    -i "${LHR_SSH_KEY}" \
    -o IdentitiesOnly=yes \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -R 80:127.0.0.1:${PORT} \
    nokey@localhost.run > "${TUNNEL_LOG}" 2>&1 &
  TUNNEL_PID=$!
}

extract_public_url() {
  awk '{for(i=1;i<=NF;i++) if ($i ~ /^https:\/\/[A-Za-z0-9.-]+$/) print $i}' "${TUNNEL_LOG}" \
    | awk '/lhr\.life|localhost\.run/ {print; exit}'
}

wait_public_url() {
  local found=""
  for _ in $(seq 1 "${MAX_URL_WAIT_SEC}"); do
    if [[ -f "${TUNNEL_LOG}" ]]; then
      found="$(extract_public_url)"
      if [[ -n "${found}" ]]; then
        echo "${found}"
        return 0
      fi
    fi
    sleep 1
  done
  return 1
}

# shellcheck source=/dev/null
source "${MINICONDA_ROOT}/etc/profile.d/conda.sh"
conda activate tenclip
cd "${ROOT}"

if [[ ! -f "${LHR_SSH_KEY}" ]]; then
  echo "未找到 localhost.run SSH 私钥: ${LHR_SSH_KEY}"
  echo "请设置 LHR_SSH_KEY=/path/to/private_key，或先创建 ~/.ssh/id_ed25519。"
  exit 1
fi
chmod 600 "${LHR_SSH_KEY}" 2>/dev/null || true

if [[ -z "${TENCLIP_VLM_MODEL:-}" && -d "${ROOT}/model/Qwen2-VL-2B-Instruct" ]]; then
  export TENCLIP_VLM_MODEL="${ROOT}/model/Qwen2-VL-2B-Instruct"
fi

echo "启动本地服务: http://127.0.0.1:${PORT}"
python app.py > "${APP_LOG}" 2>&1 &
APP_PID=$!

# 等待本地服务就绪（最多约 40 秒）
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
  echo "本地服务未就绪，请检查日志: ${APP_LOG}"
  exit 1
fi

echo "启动公网隧道（localhost.run）..."
start_tunnel
PUBLIC_URL="$(wait_public_url || true)"

if [[ -z "${PUBLIC_URL}" ]]; then
  echo "未能解析出公网 URL，请查看隧道日志: ${TUNNEL_LOG}"
  exit 1
fi

echo
echo "==============================================="
echo "公网 URL: ${PUBLIC_URL}"
echo "新闻页  : ${PUBLIC_URL}/news"
echo "Gradio  : ${PUBLIC_URL}/gradio/"
echo "日志文件: ${APP_LOG} / ${TUNNEL_LOG}"
echo "SSH 私钥: ${LHR_SSH_KEY}"
echo "按 Ctrl+C 可同时停止服务与隧道"
echo "==============================================="
echo

# 持续等待，直到任一进程退出
while true; do
  if ! kill -0 "${APP_PID}" 2>/dev/null; then
    echo "本地服务已退出，请检查: ${APP_LOG}"
    exit 1
  fi
  if ! kill -0 "${TUNNEL_PID}" 2>/dev/null; then
    echo "隧道已退出，准备自动重连..."
    sleep "${TUNNEL_RESTART_DELAY_SEC}"
    start_tunnel
    NEW_PUBLIC_URL="$(wait_public_url || true)"
    if [[ -n "${NEW_PUBLIC_URL}" ]]; then
      if [[ "${NEW_PUBLIC_URL}" != "${PUBLIC_URL}" ]]; then
        PUBLIC_URL="${NEW_PUBLIC_URL}"
        echo "隧道重连成功，新公网 URL: ${PUBLIC_URL}"
        echo "新闻页  : ${PUBLIC_URL}/news"
        echo "Gradio  : ${PUBLIC_URL}/gradio/"
      else
        echo "隧道重连成功（URL 未变化）: ${PUBLIC_URL}"
      fi
    else
      echo "重连后未解析到公网 URL，稍后继续重试。日志: ${TUNNEL_LOG}"
    fi
  fi
  sleep 2
done
