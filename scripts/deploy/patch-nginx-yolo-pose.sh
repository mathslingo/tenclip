#!/usr/bin/env bash
# 给 api.uchance.tech 增加 /yolo-pose/ 静态目录（命令行，无需点宝塔 UI）
# 用法（在云主机上）：
#   bash /root/code/tenclip/scripts/deploy/patch-nginx-yolo-pose.sh
#   bash /root/code/tenclip/scripts/deploy/patch-nginx-yolo-pose.sh --dry-run

set -euo pipefail

DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

DOMAIN="${TENCLIP_DOMAIN:-api.uchance.tech}"
ALIAS_DIR="${YOLO_POSE_DIR:-/root/code/tenclip/pose/yolo-pose-web}"
NGINX_BIN="${NGINX_BIN:-/www/server/nginx/sbin/nginx}"
[[ -x "$NGINX_BIN" ]] || NGINX_BIN="$(command -v nginx || true)"

CONF_CANDIDATES=(
  "/etc/nginx/conf.d/tenclip-api.conf"
  "/www/server/panel/vhost/nginx/${DOMAIN}.conf"
  "/etc/nginx/conf.d/${DOMAIN}.conf"
  "/etc/nginx/sites-enabled/${DOMAIN}"
)

CONF=""
for f in "${CONF_CANDIDATES[@]}"; do
  if [[ -f "$f" ]]; then
    CONF="$f"
    break
  fi
done

if [[ -z "$CONF" ]]; then
  echo "找不到 ${DOMAIN} 的 nginx 配置，候选："
  printf '  %s\n' "${CONF_CANDIDATES[@]}"
  echo "也可：export 后指定  CONF=/path/to.conf bash $0"
  exit 1
fi

# 允许环境变量覆盖
CONF="${CONF_FILE:-$CONF}"

if [[ ! -d "$ALIAS_DIR" ]]; then
  echo "静态目录不存在: $ALIAS_DIR"
  exit 1
fi
if [[ ! -f "$ALIAS_DIR/index.html" ]]; then
  echo "缺少 index.html: $ALIAS_DIR/index.html"
  exit 1
fi

MARKER="location ^~ /yolo-pose/"
if grep -qF "$MARKER" "$CONF"; then
  echo "已存在 /yolo-pose/ 配置，跳过写入: $CONF"
else
  BLOCK=$(cat <<EOF

    # --- yolo-pose static (patched by patch-nginx-yolo-pose.sh) ---
    location = /yolo-pose {
        return 301 /yolo-pose/;
    }
    location ^~ /yolo-pose/ {
        alias ${ALIAS_DIR}/;
        index index.html;
        include mime.types;
        default_type application/octet-stream;
        sendfile on;
    }
    # --- end yolo-pose ---

EOF
)

  TMP="$(mktemp)"
  cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d%H%M%S)"
  echo "备份已写: ${CONF}.bak.*"

  # 插到第一个「缩进的 location / {」之前；找不到则追加到最后一个 server 的 } 前较难，改为插入文件中首次出现的 location /
  if grep -nE '^[[:space:]]*location[[:space:]]+/[[:space:]]*\{' "$CONF" | head -1 | grep -q .; then
    LINE=$(grep -nE '^[[:space:]]*location[[:space:]]+/[[:space:]]*\{' "$CONF" | head -1 | cut -d: -f1)
    {
      sed -n "1,$((LINE - 1))p" "$CONF"
      printf '%s' "$BLOCK"
      sed -n "${LINE},\$p" "$CONF"
    } >"$TMP"
  else
    echo "未找到 location / { ，把片段追加到文件末尾（请人工检查是否在正确 server 内）"
    cat "$CONF" >"$TMP"
    printf '%s' "$BLOCK" >>"$TMP"
  fi

  if [[ "$DRY" -eq 1 ]]; then
    echo "===== dry-run 新配置片段附近 ====="
    grep -n "yolo-pose\|location /" "$TMP" | head -40
    rm -f "$TMP"
    exit 0
  fi

  mv "$TMP" "$CONF"
  echo "已写入: $CONF"
fi

if [[ -z "$NGINX_BIN" ]]; then
  echo "找不到 nginx 可执行文件"
  exit 1
fi

"$NGINX_BIN" -t
"$NGINX_BIN" -s reload
echo "nginx 已 reload"

echo "验证："
curl -sI "https://${DOMAIN}/yolo-pose/" | head -5
curl -sI "https://${DOMAIN}/yolo-pose/app.js" | head -5
