# TenClip 部署到 tennisGo（与现有微信小程序后端隔离）

目标：在已有 **tennisGo 微信小程序后端** 的腾讯云轻量服务器上，用 **已备案域名 `uchanceai.com`** 提供 TenClip API，**不改动、不抢占** 现有 Nginx 站点与端口。

| 项 | TenClip（新） | 现有 tennisGo 后端（勿动） |
|----|---------------|---------------------------|
| 域名 | `uchanceai.com` / `www.uchanceai.com` | 原有域名（各自 `server_name`） |
| Nginx 配置 | **新增** `conf.d/tenclip-uchanceai.conf` | 保持原 conf 不变 |
| 应用端口 | **127.0.0.1:7862** | 原端口（常见 8000/3000/7861 等） |
| systemd | `tenclip-uchanceai.service` | 原有 unit 不动 |
| 代码目录 | 建议 `/root/code/tenclip` | 原项目目录不动 |

Nginx 按 **Host** 分流：用户访问 `uchanceai.com` 才进 TenClip；访问原域名仍走原 upstream。**互不影响**。

---

## 0. 服务器信息（你的 tennisGo）

- 公网 IP：`1.15.27.3`
- 域名解析：`uchanceai.com`、`www.uchanceai.com` → 该 IP（轻量控制台已配置）
- 系统：CentOS（轻量应用服务器）

---

## 1. 部署前预检（SSH 登录 tennisGo）

```bash
ssh root@1.15.27.3
bash /root/code/tenclip/scripts/deploy/preflight-tennisgo.sh
```

确认 **7862 未被占用**。若占用，改 `tenclip-uchanceai.service` 里 `GRADIO_SERVER_PORT` 与 nginx 里 `proxy_pass` 端口一致。

---

## 2. 拉代码与依赖（独立目录）

```bash
cd /root
git clone <你的 tenclip 仓库> code/tenclip
# 或已有目录则 git pull

cd /root/code/tenclip
# conda 环境（与现有项目环境分开命名更安全）
conda create -n tenclip python=3.11 -y
conda activate tenclip
pip install -r requirements.txt
# 需要动作分析 GPU 时再装：
# pip install -r requirements-llm-lf.txt
conda install -c conda-forge ffmpeg -y

# 权重（按需）
# python scripts/download_vlm_weights.py
# bash scripts/copy_vlm_to_model.sh
```

**不要**在现有后端的 conda 环境里覆盖依赖，除非确认无冲突。

---

## 3. systemd（仅本机 7862，不暴露公网）

```bash
cd /root/code/tenclip
sudo cp scripts/deploy/tenclip-uchanceai.service /etc/systemd/system/

# 按实际路径修改 User、WorkingDirectory、ExecStart、PATH
sudo nano /etc/systemd/system/tenclip-uchanceai.service

sudo systemctl daemon-reload
sudo systemctl enable --now tenclip-uchanceai
sudo systemctl status tenclip-uchanceai

curl -s http://127.0.0.1:7862/api/mobile/health
# 期望: {"ok":true,...}
```

查看日志：`journalctl -u tenclip-uchanceai -f`

**注意**：不要同时手动 `python app.py` 和 systemd，否则会抢 7862 端口。

---

## 4. Nginx（新增配置文件，不改旧站）

```bash
cd /root/code/tenclip
sudo cp scripts/deploy/nginx-tenclip-uchanceai.conf.example /etc/nginx/conf.d/tenclip-uchanceai.conf

sudo nginx -t
sudo systemctl reload nginx
```

此时 HTTP 应能反代（若尚未配证书，可先临时只 listen 80 测试，再 certbot）。

### HTTPS（推荐 certbot）

```bash
sudo certbot --nginx -d uchanceai.com -d www.uchanceai.com
sudo nginx -t && sudo systemctl reload nginx
```

轻量控制台「HTTPS 未设置」也可用上述方式，或控制台一键证书（选 **仅 uchanceai.com**，不要覆盖现有站点证书配置）。

### 微信上传注意

- `listen 443 ssl` **不要**加 `http2`（小程序 uploadFile 易 reset）
- 保持 `proxy_request_buffering on;`
- 大视频超时见 conf 内 `client_body_timeout 600s`

公网自测：

```bash
curl -s https://uchanceai.com/api/mobile/health
```

---

## 5. 防火墙

轻量默认开放 80/443。TenClip **只需** 80/443 对公网；**7862 不要**对公网开放（仅 127.0.0.1）。

```bash
ss -tlnp | grep 7862
# 应显示 127.0.0.1:7862 或 0.0.0.0:7862 仅由本机 nginx 访问即可
```

---

## 6. 微信小程序配置

### 公众平台

开发管理 → 开发设置 → **服务器域名**：

- request / uploadFile / downloadFile：`https://uchanceai.com`

（根域名已备案即可；无需再单独备 `api.` 子域，除非你想用 `https://api.uchanceai.com`。）

### 本地 `miniprogram/utils/config.js`

```javascript
const LOCAL_DEV = false;
const PROD_API_BASE_URL = "https://uchanceai.com";
```

重新上传体验版；build tag 改一下便于确认版本。

### H5 网页版

复制链接会变为 `https://uchanceai.com/web`、`/web/stroke`（若已部署对应路由）。

---

## 7. 验证清单

| 检查 | 命令/操作 |
|------|-----------|
| 现有后端仍正常 | 用**原域名**打开原小程序/接口 |
| TenClip 本机 | `curl http://127.0.0.1:7862/api/mobile/health` |
| TenClip 公网 | `curl https://uchanceai.com/api/mobile/health` |
| 备案提示 | 微信聊天打开 health URL，应无「未备案」 |
| 上传 | 体验版上传短视频 |

---

## 8. 回滚（不影响现有服务）

```bash
sudo systemctl stop tenclip-uchanceai
sudo systemctl disable tenclip-uchanceai
sudo rm /etc/nginx/conf.d/tenclip-uchanceai.conf
sudo nginx -t && sudo systemctl reload nginx
```

现有站点 conf 与 unit **从未修改** 则无需其它操作。

---

## 9. 可选：API 子域

若希望 API 与官网分离，可增加 DNS `api.uchanceai.com` → `1.15.27.3`，复制一份 server 块改 `server_name api.uchanceai.com`，小程序填 `https://api.uchanceai.com`。

---

## 10. 与阿里云 ECS 的关系

备案下来后，可将 `api.uchance.tech` 迁回阿里云，或长期用 `uchanceai.com`。两套可并行一段时间，小程序改 `PROD_API_BASE_URL` 即可切换。
