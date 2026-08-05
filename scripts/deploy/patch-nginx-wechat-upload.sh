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

# 去掉 http2（微信 Cronet 对部分 http2 会 CONNECTION_RESET）
sed -i 's/listen 443 ssl http2;/listen 443 ssl;/g' "$CONF"
sed -i 's/listen \[::\]:443 ssl http2;/listen [::]:443 ssl;/g' "$CONF"
# 仅监听 IPv4，避免 [::]:443 吸引 IPv6 流量到未配置的栈
sed -i 's/listen \[::\]:443 ssl;//g' "$CONF"

# certbot 已通过 include options-ssl-nginx.conf 提供 ssl_protocols 等，勿在 server 块重复
sed -i '/^[[:space:]]*ssl_protocols TLSv1.2 TLSv1.3;$/d' "$CONF"
sed -i '/^[[:space:]]*ssl_prefer_server_ciphers off;$/d' "$CONF"

# 确保证书用 fullchain（certbot 通常已配置，缺则提示）
if grep -q 'ssl_certificate ' "$CONF" && ! grep -q 'fullchain.pem' "$CONF"; then
  echo "WARN: ssl_certificate 可能不是 fullchain.pem，微信可能因证书链不完整 reset" >&2
fi

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
