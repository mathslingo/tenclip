# 长视频上传：压缩策略与服务器带宽

> 适用：TenClip 小程序 `wx.uploadFile` → `clip.uchanceai.com`（tencentGo 轻量 2C/4G）

---

## 1. 问题本质

上传慢或失败通常由 **三段时间** 叠加：

| 阶段 | 瓶颈 | 说明 |
|------|------|------|
| 客户端压缩 | 手机 CPU | `wx.compressVideo` 对大文件需 10～60 秒 |
| 上行传输 | 用户 WiFi/4G + **服务器入站带宽** | 轻量机常见 **3～6 Mbps** 峰值 |
| 服务端落盘 | Nginx + FastAPI 分块写盘 | 已配 `proxy_request_buffering on`、512MB body |

**动作分析**后端只处理前 **约 5 分钟**（`MAX_VIDEO_DURATION_SEC=300`），但用户仍可能从相册选 **整场 30～60 分钟** 原片，导致上传体积远大于分析所需。

**击球剪辑**需要整段视频做检测，长比赛原片上传压力更大。

---

## 2. 已实施的小程序侧优化（2026-07）

`miniprogram/utils/api.js` 中 `prepareVideoForUpload` **按体积分级压缩**：

| 原片大小 | quality | bitrate (kbps) | resolution | fps |
|----------|---------|----------------|------------|-----|
| ≥ 100 MB | low | 350 | 0.45 | 24 |
| ≥ 60 MB | low | 450 | 0.5 | 24 |
| ≥ 30 MB | low | 600 | 0.65 | 24 |
| ≥ 10 MB | low | 800 | 0.75 | 30 |
| &lt; 10 MB | low | — | — | — |

- 阈值：**> 0.5 MB** 即尝试压缩（`UPLOAD_COMPRESS_ABOVE_MB`）
- 选片 **> 50 MB** 时提示使用 WiFi（`UPLOAD_WARN_SIZE_MB`）
- `wx.uploadFile` 超时 **10 分钟**（`UPLOAD_TIMEOUT_MS=600000`）

击球检测对画质不敏感， aggressive 压缩通常可接受。

---

## 3. 上传时间粗算

公式：`时间(秒) ≈ 文件大小(MB) × 8 / 带宽(Mbps)`

| 压缩后大小 | 4 Mbps 上行 | 8 Mbps 上行 |
|------------|-------------|-------------|
| 50 MB | ~100 s | ~50 s |
| 100 MB | ~200 s | ~100 s |
| 200 MB | ~400 s | ~200 s |

轻量服务器 **入站带宽**与用户上行取较小值；多用户并发时更慢。

---

## 4. 服务器侧检查清单（tencentGo）

SSH 登录后：

```bash
# 1. 本机服务正常
curl -s http://127.0.0.1:7862/api/mobile/health

# 2. Nginx 上传相关（clip 站点）
grep -E 'client_max_body_size|proxy_request_buffering|http2|quic' \
  /www/server/panel/vhost/nginx/clip.uchanceai.com.conf

# 3. 若未修补，执行
cd /root/code/tenclip && sudo bash scripts/deploy/patch-nginx-baota-clip.sh
```

**推荐 Nginx 项**（`patch-nginx-baota-clip.sh` 已包含）：

- `client_max_body_size 512m;`
- `proxy_request_buffering on;`（微信 `uploadFile` 需要）
- 443 **勿** `http2` / `quic`（大文件易 `ERR_CONNECTION_RESET`）
- `proxy_read_timeout` / `client_body_timeout` ≥ 600s

### 4.1 腾讯云轻量「带宽」

控制台 → 轻量应用服务器 → **CentOS-tennisGo** → 概要：

- 查看 **套餐带宽**（如 4 Mbps / 6 Mbps 固定，或流量包型）
- **升级套餐**可提高带宽上限（最直接）
- **防火墙**放行 80/443（与带宽无关但必查）

轻量机 **不能**像 CVM 一样单独「只买带宽」；要更快上行通常 **升配整机** 或迁 **CVM + 更高带宽**。

### 4.2 监控是否带宽打满

```bash
# 实时网卡流量（需安装 iftop 或用宝塔监控）
yum install -y iftop 2>/dev/null; iftop -i eth0
```

上传时若带宽持续顶满，升配或引导用户压缩是唯一短期手段。

---

## 5. 产品侧建议（面向用户）

已在 UI 文案中体现：

1. **优先 WiFi**
2. **较长视频自动压缩**
3. **动作分析**：提示「默认只分析前 5 分钟」——鼓励先剪短再传
4. **击球剪辑**：建议用户只传 **单盘/单局** 或先用系统相册剪到 10～15 分钟

后续可选功能（未实现）：

- 小程序内提示「仅上传前 5 分钟」（需客户端 ffmpeg 或分段，微信能力有限）
- **COS 直传** + 服务端拉取（绕开小程序经 Nginx 的长连接）
- 服务端 `ffmpeg` 接收后异步转码（不减少上传量，只减轻存储）

---

## 6. 故障对照

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 进度到 90%+ 后 reset | http2 / buffering | 跑 `patch-nginx-baota-clip.sh` |
| 10 分钟超时 | 文件过大 + 带宽低 | 加强压缩；升带宽；剪短视频 |
| 仅 4G 失败 | 备案/域名 | 确认 `clip.uchanceai.com` 已备案 |
| 压缩很久 | 原片 > 500MB | 正常；提示用户先相册裁剪 |

---

## 7. 相关文件

| 路径 | 说明 |
|------|------|
| `miniprogram/utils/config.js` | 超时、压缩阈值 |
| `miniprogram/utils/api.js` | `prepareVideoForUpload`、分级压缩 |
| `scripts/deploy/patch-nginx-baota-clip.sh` | Nginx 微信上传修补 |
| `scripts/deploy/DEPLOY_UCHANCEAI.md` | 域名与 HTTPS |
| `services/vlm_tennis.py` / `app.py` | `MAX_VIDEO_DURATION_SEC` 分析上限 |
