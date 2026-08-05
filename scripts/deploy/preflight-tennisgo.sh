#!/usr/bin/env bash
# 在 tennisGo 上部署 TenClip 前执行：检查端口/Nginx 是否与现有服务冲突
set -euo pipefail

TENCLIP_PORT="${TENCLIP_PORT:-7862}"

echo "=== 监听端口（7862 应为空，供 TenClip 使用）==="
ss -tlnp 2>/dev/null | grep -E ":${TENCLIP_PORT}\s|:7861\s|:80\s|:443\s" || true
if ss -tlnp 2>/dev/null | grep -q ":${TENCLIP_PORT} "; then
  echo "警告: ${TENCLIP_PORT} 已被占用，请改 tenclip-uchanceai.service 中的 GRADIO_SERVER_PORT"
fi

echo ""
echo "=== 现有 Nginx server_name（勿与 uchanceai.com 重复配置到别的 upstream）==="
if command -v nginx >/dev/null 2>&1; then
  grep -R "server_name" /etc/nginx/ 2>/dev/null | grep -v "#" | head -40 || true
else
  echo "未安装 nginx 或路径非 /etc/nginx"
fi

echo ""
echo "=== 现有 proxy_pass（确认现有后端用的端口，TenClip 用 ${TENCLIP_PORT}）==="
grep -R "proxy_pass" /etc/nginx/ 2>/dev/null | grep -v "#" | head -20 || true

echo ""
echo "=== 若已有 tenclip-uchanceai 配置 ==="
test -f /etc/nginx/conf.d/tenclip-uchanceai.conf && head -30 /etc/nginx/conf.d/tenclip-uchanceai.conf || echo "(尚未安装)"

echo ""
echo "预检完成。TenClip 应：单独 conf + 单独 systemd + 仅 127.0.0.1:${TENCLIP_PORT}"
