# TenClip 生产域名：tenclip.qiongjingtiyu.com

主域 **`qiongjingtiyu.com` 已 ICP 备案**（沪ICP备2025147489号-1，云资源 `1.15.27.3`）。  
TenClip API 使用 **`tenclip.qiongjingtiyu.com`** → `127.0.0.1:7862`，与 `uchanceai.com`（9098）及未备案 `clip.uchanceai.com` 分离。

| 项 | TenClip | 其他（勿动） |
|----|---------|--------------|
| 域名 | `tenclip.qiongjingtiyu.com` | `uchanceai.com` → 9098 |
| Nginx | 改 `tenclip.qiongjingtiyu.com.conf` | `youchang` / `h5` 等不动 |
| 端口 | 7862 | 9098 |

---

## 1. DNS

确认 `tenclip.qiongjingtiyu.com` 解析到 **`1.15.27.3`**：

```bash
dig +short tenclip.qiongjingtiyu.com A
```

---

## 2. 应用（应已在跑）

```bash
curl -s http://127.0.0.1:7862/api/mobile/health
sudo systemctl status tenclip-uchanceai
```

---

## 3. 宝塔 Nginx（替换旧外网隧道）

**方式 A：脚本**

```bash
cd /root/code/tenclip
git pull   # 拉取 patch 脚本
sudo bash scripts/deploy/patch-nginx-baota-tenclip-qiongjing.sh
```

**方式 B：面板**

1. 网站 → `tenclip.qiongjingtiyu.com` → **反向代理**
2. 目标 URL 改为 **`http://127.0.0.1:7862`**（删除原 `lhr.life` 隧道）
3. 配置文件补充：
   - `client_max_body_size 512m;`
   - `proxy_request_buffering on;`
   - `Upgrade` / `Connection $connection_upgrade`（Gradio 需要，见 `patch-nginx-baota-tenclip-qiongjing.sh`）

```bash
/www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload
```

验证：

```bash
curl -s http://tenclip.qiongjingtiyu.com/api/mobile/health
```

---

## 4. HTTPS

宝塔 → `tenclip.qiongjingtiyu.com` → **SSL**：

- 已备案域可用 **免费证书** 或腾讯 SSL 控制台申请 `tenclip.qiongjingtiyu.com`
- 开启 **强制 HTTPS**
- 443 配置：`listen 443 ssl;`（**勿 http2 / quic**）

```bash
curl -s https://tenclip.qiongjingtiyu.com/api/mobile/health
```

**关 WiFi、用 4G** 再开同一 URL，应返回 JSON（备案域在流量网可用）。

---

## 5. 微信小程序

公众平台 → 服务器域名：

```text
tenclip.qiongjingtiyu.com
```

（request / uploadFile / downloadFile 均填）

`miniprogram/utils/config.js`：

```javascript
const LOCAL_DEV = false;
const PROD_API_BASE_URL = "https://tenclip.qiongjingtiyu.com";
```

上传体验版，真机 **4G** 测 health + 小视频上传。

H5 链接：`https://tenclip.qiongjingtiyu.com/web/stroke`（手机推荐，优于 `/gradio/`）。

---

## 6. 与 clip.uchanceai.com 的关系

| 域名 | 建议 |
|------|------|
| `tenclip.qiongjingtiyu.com` | **生产 API**（已备案） |
| `clip.uchanceai.com` | 可停用或仅 WiFi 调试；`uchanceai.com` 未备案不宜给小程序 |

---

## 7. 回滚隧道（不推荐）

若需临时恢复外网隧道，在宝塔把反代改回旧 URL；TenClip 仍监听 7862。

---

完整 tennisGo 部署说明见 `DEPLOY_TENNISGO.md`（systemd、CentOS 7 依赖等）。
