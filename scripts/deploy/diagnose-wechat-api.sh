#!/usr/bin/env bash
# 诊断：手机浏览器能通、微信小程序 ERR_CONNECTION_RESET 且 Nginx 无 access 新行
# 用法：sudo bash scripts/deploy/diagnose-wechat-api.sh

set -euo pipefail

HOST="${1:-api.uchance.tech}"

echo "=== DNS ==="
echo -n "A:    "; dig +short "$HOST" A || true
echo -n "AAAA: "; dig +short "$HOST" AAAA || true
if dig +short "$HOST" AAAA 2>/dev/null | grep -q .; then
  echo "⚠ 存在 AAAA 记录。若 ECS 未监听 IPv6，微信可能走 IPv6 失败而浏览器走 IPv4 成功。"
  echo "  建议：DNS 控制台删除 api 的 AAAA，只保留 A 记录。"
fi

echo ""
echo "=== 本机 HTTPS ==="
curl -sf "https://${HOST}/api/mobile/health" && echo "" || echo "curl 失败"

echo ""
echo "=== 证书链（微信 Cronet 比浏览器更严）==="
echo | openssl s_client -connect "${HOST}:443" -servername "$HOST" 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates 2>/dev/null || true

echo ""
echo "=== Nginx 443 / http2 ==="
grep -E 'listen|ssl_|server_name' /etc/nginx/conf.d/*.conf 2>/dev/null | grep -v '#' || true

echo ""
echo "=== 建议下一步 ==="
echo "1. 手机微信里（非小程序）打开链接测试："
echo "   https://${HOST}/api/mobile/health"
echo "   若微信内浏览器也失败 → TLS/证书/IPv6 问题"
echo "   若微信内浏览器成功、仅小程序失败 → 再查体验版与 uploadFile 域名"
echo ""
echo "2. 另开终端抓包（小程序点「测试 API 连接」时）："
echo "   tcpdump -i any port 443 -n -c 20"
echo "   无任何 SYN → DNS/IPv6/微信未连到本机"
echo "   有 SYN 无 HTTP → TLS 握手失败，看: tail -f /var/log/nginx/error.log"
echo ""
echo "3. 应用微信兼容 Nginx 补丁："
echo "   sudo bash scripts/deploy/patch-nginx-wechat-upload.sh"
