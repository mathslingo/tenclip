# TenClip 部署到 tennisGo（与现有微信小程序后端隔离）

目标：在已有 **tennisGo 微信小程序后端**（`uchanceai.com` → `localhost:9098`）的腾讯云轻量服务器上，用 **子域名 `clip.uchanceai.com`** 提供 TenClip API，**不改动** 现有 Nginx 与 9098 服务。

| 项 | TenClip（新） | 现有 tennisGo 后端（勿动） |
|----|---------------|---------------------------|
| 域名 | **`clip.uchanceai.com`** | `uchanceai.com` → `:9098` |
| Nginx | **新建** `clip.uchanceai.com.conf` | **`uchanceai.com.conf` 不改** |
| 应用端口 | `127.0.0.1:7862` | `127.0.0.1:9098` |
| systemd | `tenclip-uchanceai.service` | 原有 unit 不动 |
| 代码目录 | `/root/code/tenclip` | 原项目目录不动 |

Nginx 按 **Host** 分流：`clip.uchanceai.com` → TenClip；`uchanceai.com` 仍走原小程序后端。**互不影响**。

> 本机为 **宝塔面板** Nginx：`--prefix=/www/server/nginx`，vhost 在 `/www/server/panel/vhost/nginx/`。

---

## 0. 服务器信息

- 公网 IP：`1.15.27.3`
- 主域已备案：`uchanceai.com`（子域 `clip.uchanceai.com` 一般随主域可用）
- 系统：CentOS 7 + 宝塔

---

## 1. DNS（先做）

在域名解析（腾讯云轻量 / DNSPod / 注册商）添加：

| 主机记录 | 类型 | 记录值 |
|----------|------|--------|
| `clip` | A | `1.15.27.3` |

生效后本机可测：

```bash
ping -c 2 clip.uchanceai.com
```

---

## 2. 应用与 systemd（7862）

```bash
bash /root/code/tenclip/scripts/deploy/preflight-tennisgo.sh

sudo cp /root/code/tenclip/scripts/deploy/tenclip-uchanceai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tenclip-uchanceai

curl -s http://127.0.0.1:7862/api/mobile/health
# 期望: {"ok":true,...}
```

日志：`journalctl -u tenclip-uchanceai -f`

**不要**同时前台 `python app.py` 与 systemd，会抢 7862。

CentOS 7 依赖安装见上文对话：`numpy==1.26.4`、`pandas==2.2.3` pin，勿装 `requirements-llm.txt`。

---

## 3. Nginx / 宝塔（方案 1：子域名）

### 方式 A：宝塔网页（推荐）

1. 宝塔 → **网站** → **添加站点**
2. 域名：`clip.uchanceai.com`（不要 PHP/数据库）
3. **反向代理** → 目标 URL：`http://127.0.0.1:7862`
4. 在反向代理或配置文件中加大上传/超时：
   - `client_max_body_size 512m;`
   - `client_body_timeout 600s;`
   - `proxy_read_timeout 600s;`
   - `proxy_request_buffering on;`
5. **SSL** → Let's Encrypt 申请 `clip.uchanceai.com`
6. 若 443 配置含 **`http2`**，请去掉（微信 uploadFile 易 reset）

### 方式 B：手写 conf

```bash
cp /root/code/tenclip/scripts/deploy/nginx-tenclip-clip-uchanceai.conf.example \
   /www/server/panel/vhost/nginx/clip.uchanceai.com.conf

/www/server/nginx/sbin/nginx -t
/www/server/nginx/sbin/nginx -s reload
```

再在宝塔为该站点申请 SSL。

### 验证

```bash
curl -s http://clip.uchanceai.com/api/mobile/health
curl -s https://clip.uchanceai.com/api/mobile/health

# 原后端应不受影响
curl -sI https://uchanceai.com/api/
```

---

## 4. 微信小程序

### 公众平台

开发管理 → 开发设置 → **服务器域名**：

- request / uploadFile / downloadFile：`https://clip.uchanceai.com`

（填子域全名，不要只填 `uchanceai.com`。）

### `miniprogram/utils/config.js`

```javascript
const LOCAL_DEV = false;
const PROD_API_BASE_URL = "https://clip.uchanceai.com";
```

改 `APP_BUILD_TAG` 后上传体验版。

H5 链接变为：`https://clip.uchanceai.com/web`、`/web/stroke`。

---

## 5. 验证清单

| 检查 | 命令/操作 |
|------|-----------|
| TenClip 本机 | `curl http://127.0.0.1:7862/api/mobile/health` |
| TenClip 公网 | `curl https://clip.uchanceai.com/api/mobile/health` |
| 原 9098 后端 | 原小程序 / `uchanceai.com` 接口正常 |
| 备案 | 微信内打开 health URL 无「未备案」 |
| 上传 | 体验版上传短视频 |

---

## 6. 回滚（不影响 9098）

```bash
sudo systemctl stop tenclip-uchanceai
sudo systemctl disable tenclip-uchanceai
rm -f /www/server/panel/vhost/nginx/clip.uchanceai.com.conf
/www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload
```

`uchanceai.com.conf` **从未修改** 则原后端无需其它操作。

---

## 7. 其它说明

- 旧示例 `nginx-tenclip-uchanceai.conf.example` 面向根域 + `/etc/nginx`；tennisGo 请用 **`nginx-tenclip-clip-uchanceai.conf.example`**。
- 备案完成后若迁回阿里云，改 `PROD_API_BASE_URL` 即可切换。
- VLM 动作分析在 CentOS 7 上通常不可用；击球检测 API 不依赖 LLM。
