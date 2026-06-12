#!/usr/bin/env bash
# 在 ECS 上修复微信小程序 uploadFile ERR_CONNECTION_RESET 常见 Nginx 项
# 用法：sudo bash scripts/deploy/patch-nginx-wechat-upload.sh

set -euo pipefail

CONF="${1:-/etc/nginx/conf.d/tenclip-api.conf}"
if [[ ! -f "$CONF" ]]; then
  echo "找不到 $CONF，请传入实际站点配置路径" >&2
  exit 1
fi

cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d%H%M%S)"

# 去掉 http2（部分微信客户端大文件上传不稳）
sed -i 's/listen 443 ssl http2;/listen 443 ssl;/g' "$CONF"
sed -i 's/listen \[::\]:443 ssl http2;/listen [::]:443 ssl;/g' "$CONF"

# 确保有上传超时（若已有则跳过插入）
grep -q 'client_max_body_size' "$CONF" || sed -i '/server_name/a\    client_max_body_size 512m;' "$CONF"
grep -q 'client_body_timeout' "$CONF" || sed -i '/client_max_body_size/a\    client_body_timeout 600s;' "$CONF"
grep -q 'client_body_buffer_size' "$CONF" || sed -i '/client_max_body_size/a\    client_body_buffer_size 16m;' "$CONF"
grep -q 'proxy_read_timeout' "$CONF" || sed -i '/client_body_timeout/a\    proxy_read_timeout 600s;\n    proxy_send_timeout 600s;' "$CONF"

sed -i 's/proxy_request_buffering off/proxy_request_buffering on/g' "$CONF"
grep -q 'proxy_request_buffering' "$CONF" || sed -i '/proxy_set_header X-Forwarded-Proto/a\        proxy_request_buffering on;' "$CONF"
grep -q 'proxy_set_header Connection' "$CONF" || sed -i '/proxy_set_header X-Forwarded-Proto/a\        proxy_set_header Connection "";' "$CONF"

nginx -t
systemctl reload nginx
echo "OK: $CONF 已更新并重载 Nginx"
