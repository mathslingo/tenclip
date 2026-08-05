# TenClip 生产域名：clip.uchanceai.com（uchanceai.com 已备案）

主域 **`uchanceai.com` 已 ICP 备案** 后，TenClip 小程序 API 使用子域 **`clip.uchanceai.com`** → `127.0.0.1:7862`。

与现有 **`uchanceai.com` → `127.0.0.1:9098`** 微信小程序旧后端 **隔离**，勿改 `uchanceai.com.conf`。

| 项 | TenClip | 现有后端（勿动） |
|----|---------|------------------|
| 机器 | tennisGo `1.15.27.3` | 同机 |
| 域名 | `clip.uchanceai.com` | `uchanceai.com` |
| Nginx | `clip.uchanceai.com.conf` | `uchanceai.com.conf` |
| 端口 | `7862` | `9098` |
| systemd | `tenclip-uchanceai.service` | 原 unit |

备选已备案域：`tenclip.qiongjingtiyu.com`（见 `DEPLOY_QIONGJING.md`），与本文二选一作为小程序 `PROD_API_BASE_URL`。

---

## 0. SSH 登录

```bash
ssh root@1.15.27.3
# 或你的用户名 + sudo
```

腾讯云轻量「防火墙」需放行：**22**、**80**、**443**（面板 → 防火墙）。

---

## 1. DNS

`clip.uchanceai.com` A 记录 → **`1.15.27.3`**

```bash
dig +short clip.uchanceai.com A
# 应输出 1.15.27.3
```

---

## 2. 应用（7862）

```bash
sudo systemctl status tenclip-uchanceai
curl -s http://127.0.0.1:7862/api/mobile/health
```

期望 JSON：`{"ok":true,"service":"tenclip",...}`

未安装时：

```bash
cd /root/code/tenclip
git pull
sudo cp scripts/deploy/tenclip-uchanceai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tenclip-uchanceai
```

依赖问题见 `DEPLOY_TENNISGO.md`（CentOS 7、numpy/pandas pin）。

---

## 3. 宝塔 Nginx

### 3.1 若无 `clip.uchanceai.com` 站点

宝塔 → 网站 → 添加站点 → `clip.uchanceai.com` → 反向代理 → `http://127.0.0.1:7862`

或复制示例：

```bash
cp /root/code/tenclip/scripts/deploy/nginx-tenclip-clip-uchanceai.conf.example \
   /www/server/panel/vhost/nginx/clip.uchanceai.com.conf
/www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload
```

### 3.2 修补上传 + Gradio WebSocket（必做）

```bash
cd /root/code/tenclip
sudo bash scripts/deploy/patch-nginx-baota-clip.sh
```

验证 HTTP：

```bash
curl -s http://clip.uchanceai.com/api/mobile/health
```

---

## 4. HTTPS

宝塔 → `clip.uchanceai.com` → **SSL**：

- 申请 Let's Encrypt 或腾讯免费证书（备案后 4G 可用）
- 开启 **强制 HTTPS**
- 443 使用 `listen 443 ssl;`（**勿 http2 / quic**，大文件 uploadFile 易 reset）

```bash
curl -s https://clip.uchanceai.com/api/mobile/health
```

**关 WiFi、用 4G** 再测同一 URL，应返回 JSON（备案生效标志）。

---

## 5. 微信小程序

公众平台 → 开发管理 → 开发设置 → **服务器域名**：

```text
clip.uchanceai.com
```

request / uploadFile / downloadFile **均填此 host**（不要带 `https://` 和路径）。

`miniprogram/utils/config.js`：

```javascript
const LOCAL_DEV = false;
const PROD_API_BASE_URL = "https://clip.uchanceai.com";
```

上传体验版 → 真机 4G 测 health + 小视频上传。

H5：`https://clip.uchanceai.com/web/stroke`

---

## 6. 一键诊断（服务器上）

```bash
bash /root/code/tenclip/scripts/deploy/preflight-tennisgo.sh
bash /root/code/tenclip/scripts/deploy/diagnose-wechat-api.sh https://clip.uchanceai.com
```

---

## 7. 常见问题

| 现象 | 处理 |
|------|------|
| 4G 打开备案提示页 | 主域备案未生效或 DNS 未指到 1.15.27.3 |
| `ERR_CONNECTION_RESET` 大视频 | `proxy_request_buffering on`；关 http2/quic |
| 域名不在 whitelist | 公众平台保存域名后重开小程序 |
| 7862 无响应 | `journalctl -u tenclip-uchanceai -n 80` |

---

## 8. 回滚

```bash
sudo systemctl stop tenclip-uchanceai
# 宝塔删除 clip 反代或改回旧目标
/www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload
```

小程序临时改回 `tenclip.qiongjingtiyu.com` 见 `DEPLOY_QIONGJING.md`。
