# 宝塔 Nginx：clip.uchanceai.com — 微信 uploadFile + Gradio WebSocket
# 用法：sudo bash scripts/deploy/patch-nginx-baota-clip.sh

set -euo pipefail

CONF="/www/server/panel/vhost/nginx/clip.uchanceai.com.conf"
EXT_DIR="/www/server/panel/vhost/nginx/extension/clip.uchanceai.com"
NGINX_CONF="/www/server/nginx/conf/nginx.conf"
NGINX="/www/server/nginx/sbin/nginx"
MAP_SNIPPET="/www/server/nginx/conf/tenclip-connection-upgrade.map"

if [[ ! -f "$CONF" ]]; then
  echo "找不到 $CONF" >&2
  exit 1
fi

cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d%H%M%S)"

# http 级 map：有 Upgrade 时走 WebSocket，否则普通 HTTP（兼顾 uploadFile）
if ! grep -q 'connection_upgrade' "$NGINX_CONF" 2>/dev/null; then
  cat > "$MAP_SNIPPET" <<'EOF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      '';
}
EOF
  # 在 http { 后 include（若尚未 include）
  if ! grep -q 'tenclip-connection-upgrade.map' "$NGINX_CONF"; then
    sed -i '/http[[:space:]]*{/a\    include '"$MAP_SNIPPET"';' "$NGINX_CONF"
  fi
  echo "已写入 $MAP_SNIPPET 并在 nginx.conf 中 include"
fi

mkdir -p "$EXT_DIR"
if [[ -f scripts/deploy/nginx-baota-clip-gradio-websocket.conf.example ]]; then
  cp scripts/deploy/nginx-baota-clip-gradio-websocket.conf.example \
    "$EXT_DIR/gradio-websocket.conf"
elif [[ -f /root/code/tenclip/scripts/deploy/nginx-baota-clip-gradio-websocket.conf.example ]]; then
  cp /root/code/tenclip/scripts/deploy/nginx-baota-clip-gradio-websocket.conf.example \
    "$EXT_DIR/gradio-websocket.conf"
fi

# 去掉 http2 / quic
sed -i 's/listen 443 ssl http2;/listen 443 ssl;/g' "$CONF"
sed -i 's/listen \[::\]:443 ssl http2;/listen [::]:443 ssl;/g' "$CONF"
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

# 通用反代：Connection 用 map（勿写死 Connection ""，会打断 Gradio WebSocket）
fix_proxy_headers() {
  local file="$1"
  if grep -q 'proxy_set_header Upgrade' "$file"; then
    return 0
  fi
  sed -i 's/proxy_set_header Connection "";/proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection $connection_upgrade;/g' "$file"
  if ! grep -q 'proxy_set_header Upgrade' "$file"; then
    sed -i '/proxy_set_header X-Forwarded-Proto/a\
        proxy_set_header Upgrade $http_upgrade;\
        proxy_set_header Connection $connection_upgrade;' "$file" 2>/dev/null || true
  fi
}

if [[ -d "$EXT_DIR" ]]; then
  for f in "$EXT_DIR"/*.conf; do
    [[ -f "$f" ]] || continue
    [[ "$f" == *gradio-websocket.conf ]] && continue
    fix_proxy_headers "$f"
  done
fi
fix_proxy_headers "$CONF"

inject_server_directives() {
  local file="$1"
  if grep -q 'client_max_body_size' "$file"; then
    return 0
  fi
  awk '
    /listen 443 ssl/ && !done {
      print
      print "    client_max_body_size 512m;"
      print "    client_body_buffer_size 16m;"
      print "    client_body_timeout 600s;"
      print "    client_header_timeout 600s;"
      print "    send_timeout 600s;"
      print "    proxy_read_timeout 600s;"
      print "    proxy_send_timeout 600s;"
      done=1
      next
    }
    { print }
  ' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
}

inject_server_directives "$CONF"

if ! grep -q 'proxy_request_buffering on' "$CONF"; then
  sed -i '/proxy_set_header Connection \$connection_upgrade/a\
        proxy_request_buffering on;' "$CONF" 2>/dev/null || true
fi

"$NGINX" -t
"$NGINX" -s reload

echo "OK: clip 站点已修补（WebSocket map + Gradio location + 上传 buffering）"
echo "手机 Gradio: https://clip.uchanceai.com/gradio/"
echo "手机 H5 推荐: https://clip.uchanceai.com/web/stroke"
