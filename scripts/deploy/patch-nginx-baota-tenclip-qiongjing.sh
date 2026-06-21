#!/usr/bin/env bash
# 宝塔：tenclip.qiongjingtiyu.com → 127.0.0.1:7862（替换旧外网隧道反代）
# 用法：cd /root/code/tenclip && sudo bash scripts/deploy/patch-nginx-baota-tenclip-qiongjing.sh

set -euo pipefail

CONF="/www/server/panel/vhost/nginx/tenclip.qiongjingtiyu.com.conf"
EXT_DIR="/www/server/panel/vhost/nginx/extension/tenclip.qiongjingtiyu.com"
NGINX_CONF="/www/server/nginx/conf/nginx.conf"
NGINX="/www/server/nginx/sbin/nginx"
MAP_SNIPPET="/www/server/nginx/conf/tenclip-connection-upgrade.map"
REPO="/root/code/tenclip"

if [[ ! -f "$CONF" ]]; then
  echo "找不到 $CONF，请在宝塔先确认站点 tenclip.qiongjingtiyu.com 存在" >&2
  exit 1
fi

cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d%H%M%S)"

# WebSocket map（http 级，与 clip 站点共用）
if ! grep -q 'connection_upgrade' "$NGINX_CONF" 2>/dev/null; then
  cat > "$MAP_SNIPPET" <<'EOF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      '';
}
EOF
  if ! grep -q 'tenclip-connection-upgrade.map' "$NGINX_CONF"; then
    sed -i '/http[[:space:]]*{/a\    include '"$MAP_SNIPPET"';' "$NGINX_CONF"
  fi
  echo "已写入 WebSocket map: $MAP_SNIPPET"
fi

mkdir -p "$EXT_DIR"
WS_EXAMPLE="$REPO/scripts/deploy/nginx-baota-qiongjing-gradio-websocket.conf.example"
if [[ -f "$WS_EXAMPLE" ]]; then
  cp "$WS_EXAMPLE" "$EXT_DIR/gradio-websocket.conf"
fi

# 外网隧道 → 本机 TenClip
sed -i 's|proxy_pass[[:space:]]*https://[^;]*lhr\.life[^;]*;|proxy_pass http://127.0.0.1:7862;|g' "$CONF"
sed -i 's|proxy_pass[[:space:]]*http://[^;]*lhr\.life[^;]*;|proxy_pass http://127.0.0.1:7862;|g' "$CONF"

# 去掉 http2 / quic
sed -i 's/listen 443 ssl http2;/listen 443 ssl;/g' "$CONF"
sed -i '/listen 443 quic;/d' "$CONF"
sed -i '/listen \[::\]:443 quic;/d' "$CONF"

sed -i 's/proxy_request_buffering off/proxy_request_buffering on/g' "$CONF"
if [[ -d "$EXT_DIR" ]]; then
  for f in "$EXT_DIR"/*.conf; do
    [[ -f "$f" ]] || continue
    [[ "$f" == *gradio-websocket.conf ]] && continue
    sed -i 's/proxy_request_buffering off/proxy_request_buffering on/g' "$f"
  done
fi

fix_proxy_headers() {
  local file="$1"
  sed -i 's/proxy_set_header Connection "";/proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection $connection_upgrade;/g' "$file"
  if ! grep -q 'proxy_set_header Upgrade' "$file"; then
    sed -i '/proxy_set_header X-Forwarded-Proto/a\
        proxy_set_header Upgrade $http_upgrade;\
        proxy_set_header Connection $connection_upgrade;' "$file" 2>/dev/null || true
  fi
}

fix_proxy_headers "$CONF"
for f in "$EXT_DIR"/*.conf; do
  [[ -f "$f" ]] || continue
  [[ "$f" == *gradio-websocket.conf ]] && continue
  fix_proxy_headers "$f"
done

if ! grep -q 'client_max_body_size' "$CONF"; then
  sed -i '/listen 80;/a\
    client_max_body_size 512m;\
    client_body_timeout 600s;\
    proxy_read_timeout 600s;\
    proxy_send_timeout 600s;' "$CONF"
fi

if ! grep -q 'proxy_pass http://127.0.0.1:7862' "$CONF"; then
  echo "WARN: 未在 $CONF 中发现 proxy_pass 127.0.0.1:7862" >&2
  echo "请在宝塔 → tenclip.qiongjingtiyu.com → 反向代理 手动设为 http://127.0.0.1:7862" >&2
fi

"$NGINX" -t
"$NGINX" -s reload

echo "OK: tenclip.qiongjingtiyu.com Nginx 已重载"
echo "验证: curl -s https://tenclip.qiongjingtiyu.com/api/mobile/health"
echo "手机 H5: https://tenclip.qiongjingtiyu.com/web/stroke"
