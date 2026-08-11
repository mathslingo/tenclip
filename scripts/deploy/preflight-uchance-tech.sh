#!/usr/bin/env bash
# 在阿里云 ECS（api.uchance.tech / 8.133.67.191）上运行摸底
set -euo pipefail

PORT="${TENCLIP_PORT:-7861}"
DOMAIN="${TENCLIP_DOMAIN:-api.uchance.tech}"
EXPECT_IP="${TENCLIP_EXPECT_IP:-8.133.67.191}"

echo "=== 本机监听 ==="
ss -tlnp 2>/dev/null | grep -E ":${PORT}\s|:80\s|:443\s" || true

echo ""
echo "=== 本机 health ==="
curl -sS --max-time 5 "http://127.0.0.1:${PORT}/api/mobile/health" || echo "(7861 无响应)"

echo ""
echo "=== DNS ${DOMAIN} ==="
dig +short "${DOMAIN}" A 2>/dev/null || getent hosts "${DOMAIN}" || true
echo "期望 A 记录: ${EXPECT_IP}"

echo ""
echo "=== 公网 HTTPS（若已配证书）==="
curl -sS --max-time 8 "https://${DOMAIN}/api/mobile/health" || echo "(HTTPS 尚未通)"

echo ""
echo "=== Nginx server_name（节选）==="
if command -v nginx >/dev/null 2>&1; then
  grep -R "server_name" /etc/nginx/ 2>/dev/null | grep -v "#" | head -40 || true
elif [[ -d /www/server/panel/vhost/nginx ]]; then
  grep -R "server_name" /www/server/panel/vhost/nginx/ 2>/dev/null | grep -v "#" | head -40 || true
else
  echo "未找到 nginx 配置目录"
fi

echo ""
echo "=== tenclip 相关 systemd ==="
systemctl list-units --type=service --all 2>/dev/null | grep -iE 'tenclip|gradio' || echo "(无匹配 unit)"

echo ""
echo "预检完成。完整步骤见 scripts/deploy/DEPLOY_UCHANCE_TECH.md"
