# TenClip 部署到 tennisGo（与现有微信小程序后端隔离）

> **生产 API 域名（已备案）**：`tenclip.qiongjingtiyu.com` → 见 **`DEPLOY_QIONGJING.md`**  
> 下文 `clip.uchanceai.com` 为历史方案（`uchanceai.com` 未备案，不宜给小程序 4G 使用）。

目标：在 **tennisGo**（`1.15.27.3`）上运行 TenClip（`127.0.0.1:7862`），与 `uchanceai.com` → `9098` 现有后端隔离。

| 项 | TenClip（推荐） | 现有后端（勿动） |
|----|-----------------|------------------|
| 域名 | **`tenclip.qiongjingtiyu.com`** | `uchanceai.com` → `:9098` |
| Nginx | `tenclip.qiongjingtiyu.com.conf` | `uchanceai.com.conf` 不改 |
| 端口 | `7862` | `9098` |
| systemd | `tenclip-uchanceai.service` | 原 unit 不动 |

宝塔 Nginx：`/www/server/panel/vhost/nginx/`。

---

## 快速上线（已备案子域）

```bash
# 1. 服务
sudo systemctl enable --now tenclip-uchanceai
curl -s http://127.0.0.1:7862/api/mobile/health

# 2. Nginx（替换 tenclip 站点旧隧道反代）
cd /root/code/tenclip
sudo bash scripts/deploy/patch-nginx-baota-tenclip-qiongjing.sh

# 3. SSL + 强制 HTTPS（宝塔）
curl -s https://tenclip.qiongjingtiyu.com/api/mobile/health
```

详见 **`scripts/deploy/DEPLOY_QIONGJING.md`**。

---

## 0. 服务器信息

- 公网 IP：`1.15.27.3`
- 备案：`qiongjingtiyu.com`（沪ICP备2025147489号-1）
- 系统：CentOS 7 + 宝塔

---

## 1. 部署前预检

```bash
bash /root/code/tenclip/scripts/deploy/preflight-tennisgo.sh
```

---

## 2. 代码与依赖（CentOS 7）

见对话记录：`numpy==1.26.4`、`pandas==2.2.3` pin；勿装 `requirements-llm.txt`。

---

## 3. systemd（7862）

```bash
sudo cp /root/code/tenclip/scripts/deploy/tenclip-uchanceai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tenclip-uchanceai
```

---

## 4. 历史：clip.uchanceai.com（未备案主域）

`uchanceai.com` 未 ICP 备案时，手机 4G 访问会被拦截。仅 WiFi 调试可用：

- `scripts/deploy/nginx-tenclip-clip-uchanceai.conf.example`
- `scripts/deploy/patch-nginx-baota-clip.sh`

---

## 5. 回滚

```bash
sudo systemctl stop tenclip-uchanceai
# 宝塔恢复 tenclip.qiongjingtiyu.com 反代或删除 extension
/www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload
```
