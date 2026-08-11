# TenClip 部署：api.uchance.tech（阿里云 ECS）

主域 **`uchance.tech` 已 ICP 备案**。小程序 API 使用子域：

| 项 | 值 |
|----|-----|
| 公网 IP | `8.133.67.191` |
| 机型 | `ecs.e-c1m1.large` · 2 vCPU · **2 GiB** · 3 Mbps |
| 系统 | Alibaba Cloud Linux 3 |
| 应用端口 | `127.0.0.1:7861`（已在跑则先 `git pull` 再重启） |
| 对外域名 | **`https://api.uchance.tech`** |
| systemd 示例 | `tenclip-uchance-tech.service` |
| Nginx 示例 | `nginx-tenclip-api.conf.example` |

> **注意内存**：2 GiB 很紧。优先保证 `/api/mobile/*`、`/api/news/*`、H5 `/web/*`。  
> Qwen2-VL 全量推理可能 OOM；动作分析可暂关或换更小模型 / 远程 VLM。  
> `pose_server`（MediaPipe/MMPose）建议另起进程或先不上线。

---

## 0. 控制台放行

阿里云 ECS → **网络与安全组** → 入方向放行：

| 端口 | 用途 |
|------|------|
| 22 | SSH |
| 80 | HTTP / 申请证书 |
| 443 | HTTPS（小程序必用） |

**不要**把 `7861` 对公网开放；只给 Nginx 反代本机 `127.0.0.1:7861`。

---

## 1. DNS

在域名解析（阿里云 DNS / 备案同账号）添加：

| 主机记录 | 类型 | 记录值 |
|----------|------|--------|
| `api` | A | `8.133.67.191` |
| `@`（可选） | A | `8.133.67.191` |

```bash
dig +short api.uchance.tech A
# 应输出 8.133.67.191
```

生效后本机可测：

```bash
curl -sI http://api.uchance.tech/
```

---

## 2. SSH 登录后摸底（已有 7861）

```bash
ssh root@8.133.67.191   # 或你的账号

ss -tlnp | grep -E ':80|:443|:7861'
curl -s http://127.0.0.1:7861/api/mobile/health
systemctl list-units --type=service --all | grep -iE 'tenclip|gradio|uvicorn' || true
ls /www/server/panel/vhost/nginx/ 2>/dev/null || ls /etc/nginx/conf.d/ 2>/dev/null
```

记下：代码目录、conda/venv 路径、是否宝塔、当前用哪个 systemd unit。

---

## 3. 更新代码并重启 7861

路径按服务器实际改（常见 `/root/code/tenclip`）：

```bash
cd /root/code/tenclip   # 或你的仓库路径
git fetch origin
git status
git pull   # 或 checkout 你要上线的分支，如 feature/pose / main

# 依赖（按需；2G 机器勿盲目 pip install 大包）
# source /root/miniconda3/bin/activate tenclip
# pip install -r requirements.txt   # 以你们线上实际文件为准

# 若已有 systemd：
sudo systemctl restart tenclip-api    # 或实际 unit 名
# 若没有 unit、是手工/screen 起的：杀掉旧进程后再起，见下一节

curl -s http://127.0.0.1:7861/api/mobile/health
curl -s 'http://127.0.0.1:7861/api/news/feed?limit=2' | head -c 400
```

期望 health 类似：`{"ok":true,...}`。

### 3.1 首次安装 systemd（没有 unit 时）

```bash
cd /root/code/tenclip
sudo cp scripts/deploy/tenclip-uchance-tech.service /etc/systemd/system/tenclip-api.service
# 编辑 User / WorkingDirectory / PATH / ExecStart 与机器一致
sudo nano /etc/systemd/system/tenclip-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now tenclip-api
sudo journalctl -u tenclip-api -n 80 --no-pager
```

应用只监听 **`127.0.0.1:7861`**，不要 `0.0.0.0` 对公网裸奔。

---

## 4. Nginx → api.uchance.tech

### 宝塔

1. 网站 → 添加站点 → `api.uchance.tech`
2. 反向代理 → `http://127.0.0.1:7861`
3. SSL → Let's Encrypt → **强制 HTTPS**
4. **关掉 HTTP/2 / QUIC**（大文件 `uploadFile` 易 `ERR_CONNECTION_RESET`）
5. 站点配置确认有：

```nginx
client_max_body_size 512m;
client_body_timeout 600s;
proxy_request_buffering on;
proxy_read_timeout 600s;
```

也可直接用仓库示例（证书路径按 certbot/宝塔改）：

```bash
cp /root/code/tenclip/scripts/deploy/nginx-tenclip-api.conf.example \
   /www/server/panel/vhost/nginx/api.uchance.tech.conf
# 或 /etc/nginx/conf.d/api.uchance.tech.conf
nginx -t && nginx -s reload
# 宝塔：/www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload
```

### 验证

```bash
curl -s http://api.uchance.tech/api/mobile/health
curl -s https://api.uchance.tech/api/mobile/health
# 关 WiFi、用手机 4G 浏览器打开同一 HTTPS URL，应返回 JSON（备案生效）
```

一键诊断：

```bash
bash /root/code/tenclip/scripts/deploy/diagnose-wechat-api.sh https://api.uchance.tech
```

---

## 5. 微信小程序配置

公众平台 → 开发管理 → 开发设置 → **服务器域名**（不要带 `https://`）：

```text
api.uchance.tech
```

勾选/填写到：**request合法域名**、**uploadFile**、**downloadFile**。  
若用 web-view：业务域名也加 `api.uchance.tech`，并按平台要求放校验文件。

`miniprogram/utils/config.js`：

```javascript
const LOCAL_DEV = false;
const PROD_API_BASE_URL = "https://api.uchance.tech";
```

本地调试仍用 `LOCAL_DEV = true`。上体验版前改 `APP_BUILD_TAG`，真机 **4G** 测 health + 小视频上传。

---

## 6. 新闻库 / 定时抓取（可选）

```bash
# 有库则：
curl -s 'http://127.0.0.1:7861/api/news/feed?limit=5'
# 空库则 ingest（注意服务器出口与源站限制）：
# curl -s -X POST 'http://127.0.0.1:7861/api/news/ingest?limit_per_source=20'
```

定时：见 `scripts/install_news_cron_http.sh` / `docs/news_pipeline.md`。

---

## 7. 姿态检测 pose_server（小程序「实时关键点」需要）

小程序生产配置打到：

- `GET  https://api.uchance.tech/health`
- `POST https://api.uchance.tech/detect`

主 API（7861）**没有**这两条路由，必须另起 `pose_server.py`（推荐 MediaPipe CPU）并用 Nginx 反代。

### 7.1 依赖（tenclip 环境）

```bash
conda activate tenclip
pip install flask flask-cors opencv-python-headless pillow
pip install 'mediapipe==0.10.14'   # 与 pose_server 兼容；勿装 1.0+
```

### 7.2 启动

```bash
cd /root/code/tenclip
sudo cp scripts/deploy/tenclip-pose.service /etc/systemd/system/
# 核对 PATH / WorkingDirectory
sudo systemctl daemon-reload
sudo systemctl enable --now tenclip-pose
curl -s http://127.0.0.1:5000/health
# 期望: {"status":"ok","backend":"MediaPipe",...}
```

手动试跑：

```bash
cd /root/code/tenclip/pose
HOST=127.0.0.1 PORT=5000 python pose_server.py
```

### 7.3 Nginx

把 `scripts/deploy/nginx-pose-locations.conf.example` 中的三个 `location` 粘进 `api.uchance.tech` 的 **443 server**（放在 `location /` 之前），然后：

```bash
nginx -t && nginx -s reload
# 宝塔: /www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload
curl -s https://api.uchance.tech/health
```

### 7.4 小程序

- `config.js`：`LOCAL_DEV=false` 时已指向 `PROD_API_BASE_URL` 的 `/detect`、`/health`（无需再改）
- 「分析」页里关键点入口需在「我的」打开 **开发者模式**
- 「我的」快捷入口「实时关键点」也可进；请用**真机**（模拟器摄像头能力弱）

---

## 8. 检查清单

- [ ] DNS `api` → `8.133.67.191`
- [ ] 安全组 80/443
- [ ] `curl 127.0.0.1:7861/api/mobile/health` OK
- [ ] `https://api.uchance.tech/api/mobile/health` OK（含 4G）
- [ ] 公众平台合法域名已填
- [ ] `LOCAL_DEV = false` 后上传体验版
- [ ] 发现页 / 剪辑上传抽测

---

## 9. 常见问题

| 现象 | 处理 |
|------|------|
| 4G 打开备案拦截页 | 备案未生效 / DNS 未指到本机 / 用了未备案子域 |
| `ERR_CONNECTION_RESET` 上传 | 关 http2；`proxy_request_buffering on`；加大 `client_max_body_size` |
| health 通但新闻空 | 跑 ingest 或临时 Mock |
| OOM / 服务反复重启 | 关 VLM；减 worker；加 swap（治标） |
| 7861 已被占用无法起 | `ss -tlnp \| grep 7861`，停旧进程再启 systemd |

---

## 10. 与旧域名关系

| 域名 | 机器 | 说明 |
|------|------|------|
| `api.uchance.tech` | `8.133.67.191:7861` | **本次目标** |
| `clip.uchanceai.com` | `1.15.27.3:7862` | 旧 tennisGo，可逐步切流 |
| `tenclip.qiongjingtiyu.com` | 见 `DEPLOY_QIONGJING.md` | 备选 |

小程序只配一个生产 `PROD_API_BASE_URL` 即可。
