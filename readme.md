# TenClip

在**有限本机 GPU**上跑通网球视频链路（**剪辑** + **Qwen2-VL 动作理解**），并扩展**网坛资讯与内容站**相关能力。模型与推理数据默认在本地（权重首次从 ModelScope/HF 拉取后缓存；视频由用户本地上传）。


| 模块           | 路径                      | 说明                                                              |
| ------------ | ----------------------- | --------------------------------------------------------------- |
| **主应用**      | `app.py`、`run-wsl.sh`   | Gradio：剪辑 / 动作分析；RSS 网坛新闻 H5（`/news`）                           |
| **Core API** | `subprojects/core_api/` | FastAPI：新闻、球员、比赛、视频 CRUD、JWT；小红书工具路由                            |
| **VLM API**  | `subprojects/vlm_api/`  | 本地 Qwen2-VL HTTP 推理（默认 **7862**）；接口见 `[vlm-api.md](vlm-api.md)` |
| **用户站**      | `web/`                  | React + Ant Design（Vite，开发端口 **5174**）                          |
| **管理后台**     | `admin/`                | React + Ant Design（Vite，开发端口 **5173**）                          |
| **小红书抓取**    | `subprojects/xhs_note/` | 按 24 位笔记 ID + Cookie 拉取标题/封面等（独立于旧 `xhs_preview`）               |
| **微信小程序**    | `miniprogram/`          | 击球剪辑 + 大模型动作分析（调用 `app.py` 的 `/api/mobile/`*）                   |


子项目安装、联调、npm/WSL 排错：`[subprojects/README.md](subprojects/README.md)`。小程序说明：`[miniprogram/README.md](miniprogram/README.md)`。

主应用推理栈与 [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) 对齐：默认用其 `ChatModel`（可回退 Transformers）。网球域 SFT 可在同环境训练后，将 `TENCLIP_VLM_MODEL` 指向合并后的本地目录。

---



## 开发约定（本项目统一采用）


| 项         | 要求                                                                                                                                    |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 系统        | **WSL2 + Ubuntu**（与 Windows 同机即可）                                                                                                     |
| Python 环境 | **Conda 环境名必须为** `tenclip`（Miniconda/Anaconda 均可）                                                                                     |
| 本地权重      | 放在 `**model/Qwen2-VL-2B-Instruct/**` 时，`app.py` 会自动设置 `TENCLIP_VLM_MODEL`，推理直接读 `model/`                                              |
| 换行符       | 文本文件统一 **LF**（根目录 `.editorconfig`、`.gitattributes`）。若在 Windows 上保存成 **CRLF**，WSL 下运行 `*.sh` 易出现 `set: invalid option`、路径含 `$'\r'` 等问题 |


首次进入仓库建议在 WSL 里执行（可选）：

```bash
chmod +x run-wsl.sh download-vlm-conda.sh scripts/verify_wsl_env.sh
bash scripts/verify_wsl_env.sh
```

---



## 子项目快速启动（Core API + 用户站）

在 **WSL** 仓库根目录 `~/code/tenclip` 准备两个终端（不要用 `\\wsl.localhost\...` 路径跑 npm）：

**终端 1 — API（必须先起）**

```bash
conda activate tenclip
pip install -r requirements-subproject-core-api.txt   # 首次
python3 -m uvicorn subprojects.core_api.app:app --host 127.0.0.1 --port 8000

# 在服务器上 快速重启
sudo systemctl daemon-reload && sudo systemctl restart tenclip-uchanceai && sleep 2 && curl -s http://127.0.0.1:7862/api/mobile/health
# 若只改了代码、没动 unit 文件，可简化为：
sudo systemctl restart tenclip-uchanceai && sleep 2 && curl -s http://127.0.0.1:7862/api/mobile/health

```

文档：`http://127.0.0.1:8000/docs` · 健康检查：`GET /health`

**终端 2 — 用户站**

```bash
cd ~/code/tenclip/web
npm install   # Node >= 18，须为 WSL 内 npm
npm run dev -- --host 0.0.0.0
```

浏览器一般为 **[http://127.0.0.1:5174](http://127.0.0.1:5174)**；`/api` 由 Vite 代理到本机 **8000**（见 `web/vite.config.ts`）。

**管理后台（可选）**：`cd admin && npm install && npm run dev`（默认 **5173**）。

**自检**：`python3 scripts/verify_core_api.py` · **小红书笔记（需 Cookie）**：`python3 scripts/xhs_note_fetch.py <24位note_id>`（Cookie 见下文与 `subprojects/README.md`）。

一键脚本（若 `.sh` 遇 CRLF 报错，见 `subprojects/README.md`）：`bash scripts/start_core_api.sh`、`bash scripts/start_web.sh`。

---



## 微信小程序启动（击球剪辑 + 动作分析）

小程序依赖**主应用** `app.py`（不是 Core API `8000` 端口）。在 **WSL** 仓库根目录：

**1. 启动后端（终端 1）**

```bash
conda activate tenclip
cd ~/code/tenclip
# 小程序 / 真机调试须监听所有网卡（勿仅用 127.0.0.1）
GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh
# 等价：GRADIO_SERVER_NAME=0.0.0.0 python app.py
```

默认端口 `7861`。WSL 下查本机 IP：`hostname -I | awk '{print $1}'`。  
动作分析需本机 VLM 权重与 GPU；击球剪辑主要依赖 **ffmpeg**。

**2. 配置小程序 API 地址（必做，否则会报** `url not in domain list`**）**

编辑 `miniprogram/utils/config.js`：

```js
const LOCAL_DEV = true;
const LOCAL_API_HOST = "http://172.22.x.x:7861";  // WSL 里 hostname -I 得到的 IP
```

**3. 微信开发者工具 → 详情 → 本地设置**

勾选 **「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**（仅本地调试；`project.config.json` 里 `urlCheck` 已为 `false`）。

上线时：`LOCAL_DEV = false`，`PROD_API_BASE_URL` 填 HTTPS 域名，并在[微信公众平台](https://mp.weixin.qq.com) → 开发设置 → 服务器域名 配置 `request` / `uploadFile` 合法域名。

上传超时默认 **10 分钟**（`UPLOAD_TIMEOUT_MS`）。

微信公众平台 → **开发设置 → 服务器域名**：将同一域名加入 `request`、`uploadFile` 合法域名（上线必须 HTTPS）。

**4. 用微信开发者工具打开项目**

1. 安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)。
2. **导入项目** → 目录选仓库内 `miniprogram/`（不是仓库根目录）。
3. `project.config.json` 里把 `appid` 换成你的小程序 AppID（体验可用测试号）。
4. 编译后底部切换：**击球剪辑** | **动作分析**。


| Tab  | 页面                      | 后端接口                                                     |
| ---- | ----------------------- | -------------------------------------------------------- |
| 击球剪辑 | `pages/stroke-extract/` | `POST /api/mobile/stroke-extract/submit` + 任务轮询 + 下载 MP4 |
| 动作分析 | `pages/action-analyze/` | `POST /api/mobile/analyze-video/submit` + 任务轮询           |


**5. 可选自检（后端已启动时）**

```bash
curl -s http://127.0.0.1:7861/api/mobile/events | head
```

H5 对照页（同一后端）：`http://127.0.0.1:7861/web`（动作分析）、Gradio `http://127.0.0.1:7861/gradio`（击球提取标签页）。

**6. 常见报错**


| 报错                                                   | 处理                                                                                                                 |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `url not in domain list` / `your-domain.example.com` | 改 `config.js` 的 `LOCAL_API_HOST`；勾选「不校验合法域名」；勿保留占位域名                                                               |
| `Error: timeout` / 上传卡住                              | 小程序端 10 分钟；**Nginx 须设** `client_body_timeout 600s`（默认 60s 会断大文件）；ECS 带宽 3Mbps 时 100MB+ 需数分钟，看上传百分比                 |
| `uploadFile:fail ERR_CONNECTION_RESET`               | 多为 Nginx `proxy_request_buffering off` 或 `tenclip-api` 重启；见 `nginx-tenclip-api.conf.example`（应为 `on`）；小程序会自动重试 3 次 |
| WSL 连不上                                              | `GRADIO_SERVER_NAME=0.0.0.0` 启动；`LOCAL_API_HOST` 用 `hostname -I` 的 IP（模拟器可试 `127.0.0.1`）                           |
| 轮询偶发超时                                               | 会自动重试                                                                                                              |


Windows 侧可先测通：`curl http://<WSL_IP>:7861/api/mobile/events`

### 提交微信审核 / 上线：后台不能跑在本机

截图里的 `connect ECONNREFUSED 127.0.0.1:7861` 说明：**审核员手机访问不到你电脑上的 WSL**。`bash run-wsl.sh` 仅适合开发；**审核与正式用户都必须连公网 HTTPS API**。

```
┌─────────────┐     HTTPS      ┌──────────────┐    反代     ┌─────────────────┐
│ 微信小程序   │ ──────────────►│ api.你的域名  │ ─────────►│ 云服务器 app.py │
│ (用户/审核)  │  uploadFile    │  (Nginx+证书) │  :7861    │ systemd 常驻     │
└─────────────┘                └──────────────┘            └─────────────────┘
```

**推荐做法（与现有「生产部署」一致）**


| 步骤          | 内容                                                                                         |
| ----------- | ------------------------------------------------------------------------------------------ |
| 1. 买云主机     | 腾讯云 CVM 等，有**公网 IP**；域名 **ICP 备案**（大陆）                                                     |
| 2. 装环境      | Ubuntu + conda `tenclip` + `ffmpeg`；击球剪辑只需 CPU；动作分析需 **GPU 机** 或审核期先只开击球 Tab               |
| 3. 部署代码     | `git clone` → 权重放到 `model/` 或 `TENCLIP_VLM_MODEL`                                          |
| 4. 常驻进程     | `scripts/deploy/tenclip-api.service`（systemd，`Restart=always`）                             |
| 5. HTTPS 反代 | `scripts/deploy/nginx-tenclip-api.conf.example`（`client_max_body_size 512m`）               |
| 6. 小程序配置    | `miniprogram/utils/config.js`：`LOCAL_DEV = false`，`PROD_API_BASE_URL = "https://api.你的域名"` |
| 7. 微信公众平台   | 开发设置 → 服务器域名：`request`、`uploadFile`、`downloadFile` 均填 `https://api.你的域名`                   |
| 8. 提审前自测    | 手机微信（非开发者工具）打开体验版，上传短视频；`curl https://api.你的域名/api/mobile/health`                          |


**不能保证后台运行的方式（勿用于审核）**

- 家里 WSL + `127.0.0.1` / 局域网 IP
- `scripts/run-public-wsl.sh` 临时隧道（域名会变，无法写进小程序合法域名）

**审核备注建议**：在「版本说明 / 测试说明」写明体验账号（若需要）、API 已 7×24 常驻、仅支持网球视频上传等。

配置与 Nginx/systemd 示例见 `scripts/deploy/`。

### 云服务器运维（小程序 API / `app.py`）

以下以阿里云 ECS 项目路径 `/root/code/tenclip` 为例；若你的路径不同，把命令里的目录改成实际 `git clone` 位置即可。

**一次性安装 systemd 单元**

```bash
conda activate tenclip
cd /root/code/tenclip
which python   # 记下路径，须与 service 里 ExecStart 一致

cp /root/code/tenclip/scripts/deploy/tenclip-api.service /etc/systemd/system/
sed -i 's|/home/hayden/code/tenclip|/root/code/tenclip|g' /etc/systemd/system/tenclip-api.service
sed -i 's|User=hayden|User=root|g' /etc/systemd/system/tenclip-api.service
sed -i 's|/home/hayden/miniconda3/envs/tenclip/bin/python|'"$(which python)"'|g' /etc/systemd/system/tenclip-api.service
# 仅跑击球剪辑、无 VLM 时可删：sed -i '/TENCLIP_VLM_MODEL/d' /etc/systemd/system/tenclip-api.service

systemctl daemon-reload
systemctl enable --now tenclip-api
```

**常用运维命令**


| 操作          | 命令                                            |
| ----------- | --------------------------------------------- |
| 查看状态        | `systemctl status tenclip-api`                |
| 启动          | `systemctl start tenclip-api`                 |
| 停止          | `systemctl stop tenclip-api`                  |
| 重启（改代码/配置后） | `systemctl restart tenclip-api`               |
| 开机自启已开      | `systemctl enable tenclip-api`                |
| 实时日志        | `journalctl -u tenclip-api -f`                |
| 最近 200 行日志  | `journalctl -u tenclip-api -n 200 --no-pager` |


**健康检查与小程序 API 自检**

```bash
# 本机探活
curl -s http://127.0.0.1:7861/api/mobile/health

# 上传提交 + 任务查询通路（冒烟测试，非真实视频）
bash /root/code/tenclip/scripts/verify_miniprogram_api.sh http://127.0.0.1:7861
```

HTTPS 域名配置完成后，外网再测：

```bash
curl -s https://api.你的域名/api/mobile/health
```

**任务失败「未找到 ffmpeg」**

`conda list` 有 ffmpeg 但 systemd 里找不到：交互式 shell 会 `conda activate` 把 `env/bin` 加入 PATH，**systemd 不会**。代码已会从 `python` 同目录找 `ffmpeg`；更新代码后 `git pull` 并 `systemctl restart tenclip-api`。也可在 service 里加 `Environment=PATH=.../envs/tenclip/bin:...`（见 `scripts/deploy/tenclip-api.service`）。

ECS 上自检：

```bash
/root/miniconda3/envs/tenclip/bin/ffmpeg -version   # 路径按实际 conda 位置
systemctl show tenclip-api -p Environment
```

**上传超时（体验版传视频失败）**

Nginx 默认 `client_body_timeout` **仅 60 秒**，大于约 15–20MB 的视频在 3Mbps 带宽下常超过 60 秒即被断开。在 ECS 上编辑 `/etc/nginx/conf.d/tenclip-api.conf`（或 certbot 生成的站点配置），在 `server { ... }` 内加入：

```nginx
client_max_body_size 512m;
client_body_timeout 600s;
client_header_timeout 600s;
send_timeout 600s;
proxy_read_timeout 600s;
proxy_send_timeout 600s;
```

然后 `nginx -t && systemctl reload nginx`。完整示例见 `scripts/deploy/nginx-tenclip-api.conf.example`。

上传时同时看：`journalctl -u tenclip-api -f`（是否收到请求）、`tail -f /var/log/nginx/error.log`。先用 **30 秒内、<20MB** 短视频验证通路，再试长片。

**注意**

- 手动 `python app.py` 与 systemd **不要同时占 7861**；切到 systemd 前先停掉前台进程。
- `git pull` 更新代码后执行：`systemctl restart tenclip-api`。
- 运行时上传目录 `data/uploads/`、`data/stroke_outputs/` 已在 `.gitignore`，勿提交大视频。

---



## 分阶段路线图（同步维护）

以下为**计划与当前进度**，后续迭代会继续在本文更新勾选状态。

### 阶段 1：环境与本地权重（当前重点）


| 步骤  | 内容                                                                                                         | 状态                    |
| --- | ---------------------------------------------------------------------------------------------------------- | --------------------- |
| 1.1 | WSL2 Ubuntu + `conda activate tenclip` + GPU 可用（`nvidia-smi` / `torch.cuda.is_available()`）                | ⬜ 由你在本机确认             |
| 1.2 | 运行 `bash scripts/verify_wsl_env.sh` 通过                                                                     | ⬜                     |
| 1.3 | **本地下载 VLM 权重**：`python scripts/download_vlm_weights.py`（可 HF + `HF_ENDPOINT=https://hf-mirror.com`）       | ✅ 可已完成（见 `model/`）    |
| 1.4 | （推荐）复制到项目：`bash scripts/copy_vlm_to_model.sh`，`.env` 设置 `TENCLIP_VLM_MODEL=.../model/Qwen2-VL-2B-Instruct` | ⬜ 见 `model/README.md` |
| 1.5 | （可选）`export MODELSCOPE_CACHE=~/modelscope-cache` 把缓存固定到大磁盘                                                 | ⬜                     |


**默认模型**：`Qwen/Qwen2-VL-2B-Instruct`（约 2B，适合 6GB 级显存配合 4bit/少帧）。

### 阶段 2：Demo 闭环（功能已具备，阶段 1 完成后验收）


| 步骤  | 内容                                       | 状态      |
| --- | ---------------------------------------- | ------- |
| 2.1 | `bash run-wsl.sh` 启动 Gradio              | ⬜       |
| 2.2 | 「视频剪辑」：上传 → 按秒裁剪 → 下载                    | ✅ 已实现   |
| 2.3 | 「网球动作分析」：上传 → 省显存模式 → 生成中文指导（基于抽帧，非专业动捕） | ✅ 已实现   |
| 2.4 | 6GB 显存：界面保持 **省显存**，长视频先剪辑再分析            | ✅ 策略已内置 |




### 阶段 3：数据与可选微调（本地数据）


| 步骤  | 内容                                                               | 状态     |
| --- | ---------------------------------------------------------------- | ------ |
| 3.1 | 用剪辑功能准备短片段，自建「视频帧 + 文本标签」数据规范（README 后续可补样例）                     | ⬜      |
| 3.2 | 仓库内已有 `data/` 下 mock 与 `dataset_info.json`，仅供 LLaMA-Factory 实验参考 | ✅ 占位数据 |
| 3.3 | 使用 LLaMA-Factory + 合并权重目录，设置 `TENCLIP_VLM_MODEL` 指向本地目录          | ⬜ 可选   |




### 阶段 4：加固与交付


| 步骤  | 内容                                 | 状态      |
| --- | ---------------------------------- | ------- |
| 4.1 | `test_trim2.py` 等烟雾测试              | ✅       |
| 4.2 | 环境变量与故障排查（OOM、仅 CPU）               | ✅ 见下文表格 |
| 4.3 | （可选）统一 `requirements` 与 WSL 已装版本锁定 | ⬜       |




### 阶段 5：网坛新闻（新增产品线）


| 步骤  | 内容                                               | 状态                |
| --- | ------------------------------------------------ | ----------------- |
| 5.1 | 设计双列下滑 H5（图文混排，类似小红书瀑布流）                         | ✅ 第一版已接入 `/news`  |
| 5.2 | 构建内容池：每日抓取主流网坛来源（先 RSS，再扩展站点解析）并入库               | ✅ RSS 抓取 + SQLite |
| 5.3 | 推荐系统：基于偏好标签（球员/技战术）+ 新鲜度 + 反馈信号排序                | ✅ 基础版             |
| 5.4 | 用户画像与反馈闭环：保存用户偏好标签，记录点击/点赞/不感兴趣，持续改进排序           | ✅ 已打通 API         |
| 5.5 | 调度与治理：定时任务（每天 2-6 次）、去重、来源白名单、失败重试、内容质量审计（低质/重复） | ⬜ 待你确认部署方式        |
| 5.6 | 算法升级：在基础排序稳定后，再加协同过滤（用户-文章隐式反馈矩阵）与多臂探索           | ⬜ 下一阶段            |




### 阶段 6：Core API 与前端（与 Gradio 并行）


| 步骤  | 内容                                                                    | 状态       |
| --- | --------------------------------------------------------------------- | -------- |
| 6.1 | `subprojects/core_api`：新闻/球员/比赛/视频 CRUD、JWT、SQLite `data/core_api.db` | ✅        |
| 6.2 | `web/` 用户站：首页、新闻/比赛详情、小红书 explore 卡片展示                                | ✅ 第一版    |
| 6.3 | `admin/` 管理后台：资源 CRUD                                                 | ✅ 第一版    |
| 6.4 | `subprojects/xhs_note`：按笔记 ID + Cookie 抓取；`scripts/xhs_note_fetch.py` | ✅        |
| 6.5 | 生产：构建静态资源 + Nginx 反代 `/api`、绑定腾讯云域名                                   | ⬜ 见下文部署节 |


---



## WSL 快速开始（主路径 · Gradio）

```bash
cd ~/code/tenclip   # 你的克隆路径

# 1）自检（不下载模型）
bash scripts/verify_wsl_env.sh

# 2）下载 VLM 到本机缓存（首次必做，体积大）
bash download-vlm-conda.sh

# 3）启动 Web（Windows 浏览器访问即可）
bash run-wsl.sh
```

如需“本地服务 + 公网可访问 URL”一键启动（临时隧道）：

```bash
cd ~/code/tenclip
chmod +x scripts/run-public-wsl.sh
bash scripts/run-public-wsl.sh
```

脚本会自动打印公网 URL（基于 `localhost.run`），并在你按 `Ctrl+C` 时一并关闭本地服务与隧道。

浏览器打开：`http://127.0.0.1:7860`  
若要从局域网访问，可在 `.env` 或环境中设置 `GRADIO_SERVER_NAME=0.0.0.0`（见 `env.example`）。

`run-wsl.sh` 默认使用 `~/miniconda3`，若你的 Conda 在别处：

```bash
export MINICONDA_ROOT=/你的路径/miniconda3
bash run-wsl.sh
```



### 下载慢：换 Hugging Face、镜像或代理

ModelScope 若特别慢，可**改走 Hugging Face**，并配合**国内镜像端点**（由 `huggingface_hub` 读取 `HF_ENDPOINT`）：

```bash
export TENCLIP_MODEL_DOWNLOAD_SOURCE=huggingface
export HF_ENDPOINT=https://hf-mirror.com
# 与上面等价、便于写进 .env 的别名：
# export TENCLIP_HF_ENDPOINT=https://hf-mirror.com

python scripts/download_vlm_weights.py
# 或一行指定镜像（不改环境变量）：
# python scripts/download_vlm_weights.py --source huggingface --hf-endpoint https://hf-mirror.com
```

**注意**：推理时也要用同一来源，请保持 `TENCLIP_MODEL_DOWNLOAD_SOURCE` 与下载时一致（或直接把 `TENCLIP_VLM_MODEL` 设为已下载的**本地目录**，则不再请求远程）。

走**系统代理**（Clash、V2 等）时，一般设置即可（ModelScope 与 HF 通常都会走）：

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
```

下载脚本启动时会打印当前**下载源、HF_ENDPOINT、是否检测到代理变量**，便于排查。

---



## 功能与限制



### 剪辑

- 支持：`.mp4`、`.mov`、`.avi`
- 输出：`libx264` + `aac` 的 `.mp4`



### 动作分析（视频理解）

- **时长**：默认只分析前 **300 秒**；更长请先用剪辑截断。
- **方式**：均匀 **抽帧** + **Qwen2-VL-2B** 视觉理解；不是逐帧骨骼识别，结论仅供学习参考。
- **本地**：权重缓存在本机；上传视频不离开你的机器（除非你自己配置云端）。



### 弱 GPU（如 RTX 3060 Laptop 6GB）

- 界面选 **「省显存（弱显卡推荐）」**；后台对 LLaMA-Factory 路径在 eco/balanced 下倾向 **4bit**。
- OOM 时：再剪短、关其它占显存程序，或 `TENCLIP_FORCE_CPU=1`（很慢）。

---



## 环境变量（摘要）

完整说明见 `env.example`。


| 变量                                               | 含义                                                                                           | 默认                          |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------- | --------------------------- |
| `TENCLIP_VLM_MODEL`                              | 本地模型目录，或远程 ID（用于首次下载）                                                                        | `Qwen/Qwen2-VL-2B-Instruct` |
| `TENCLIP_MODEL_DOWNLOAD_SOURCE`                  | `modelscope` / `huggingface`                                                                 | `modelscope`                |
| `HF_ENDPOINT`                                    | HF Hub 镜像根 URL，如 `https://hf-mirror.com`                                                     | 未设置（官方 hub）                 |
| `TENCLIP_HF_ENDPOINT`                            | 与 `HF_ENDPOINT` 同义；未设 `HF_ENDPOINT` 时生效                                                      | 未设置                         |
| `HTTP_PROXY` / `HTTPS_PROXY`                     | 下载走系统代理                                                                                      | 未设置                         |
| `TENCLIP_INFER_BACKEND`                          | `auto` / `llamafactory` / `transformers`                                                     | `auto`                      |
| `TENCLIP_PROMPT_PROFILE`                         | 推理提示词档位：`default` / `compact` / `step_by_step` / `step_by_step_v2` / `motion_deep`           | `default`                   |
| `TENCLIP_PROMPT_APPEND`                          | 追加到系统提示词末尾的额外要求（用于快速试验）                                                                      | 未设置                         |
| `MODELSCOPE_CACHE`                               | ModelScope 缓存目录                                                                              | 系统默认                        |
| `TENCLIP_MAX_VIDEO_SEC`                          | 分析时长上限（秒）                                                                                    | `300`                       |
| `TENCLIP_MAX_NEW_TOKENS`                         | 覆盖 VLM **解码长度上限**（`max_new_tokens`）；过小会导致中文长回答**中途截断**；不设则按模式默认（省显存约 1024，平衡约 1536，质量约 2048） | 未设置（用模式默认）                  |
| `TENCLIP_NEWS_HTTP_TIMEOUT_SEC`                  | 网坛新闻：单次 HTTP 读超时（秒）                                                                          | `12`                        |
| `TENCLIP_NEWS_SOURCE_TIMEOUT_SEC`                | 网坛新闻：**单个来源**抓取+解析总预算（秒），超时跳过该来源                                                             | `28`                        |
| `TENCLIP_NEWS_SOURCES_CONFIG`                    | 网坛新闻：来源列表 JSON 路径（不设则用仓库 `config/news_sources.json`）                                         | 未设置                         |
| `TENCLIP_FORCE_CPU`                              | 强制走 CPU                                                                                      | 未设置                         |
| `GRADIO_SERVER_NAME` / `GRADIO_SERVER_PORT`      | 监听地址与端口                                                                                      | `127.0.0.1` / `7860`        |
| `TENCLIP_CORE_API_DATABASE_URL`                  | Core API 数据库（SQLite 默认 `data/core_api.db`）                                                   | 见 `env.example`             |
| `TENCLIP_CORE_API_JWT_SECRET`                    | Core API JWT 密钥（**生产必设**）                                                                    | 未设置                         |
| `TENCLIP_XHS_COOKIE` / `TENCLIP_XHS_COOKIE_FILE` | 小红书抓取 Cookie（默认文件 `data/xhs_cookie.txt`，已 gitignore）                                         | 见 `subprojects/README.md`   |


Core API、小红书、`web`/`admin` 的变量与接口细节见 `env.example` 与 `[subprojects/README.md](subprojects/README.md)`。

---



## 生产部署（腾讯云域名）

主应用 Gradio 与子项目 **可分开部署**。常见做法：在 **腾讯云 CVM** 上跑 Nginx，域名解析 **A 记录** 到公网 IP，由 Nginx **反向代理**（「透传」）到本机进程：


| 对外路径                    | 后端                       | 说明                                 |
| ----------------------- | ------------------------ | ---------------------------------- |
| `/`                     | `web/dist` 静态文件          | `cd web && npm run build`          |
| `/api/`                 | `http://127.0.0.1:8000/` | 与开发时 Vite 代理一致；API 仅监听 `127.0.0.1` |
| （可选）`admin.example.com` | `admin/dist`             | 管理后台单独子域名                          |
| （可选）Gradio              | `127.0.0.1:7860`         | 视频 Demo，可单独子域名                     |


要点：

1. **DNS**：在腾讯云 DNSPod 将 `@` / `www` 指到 CVM 公网 IP；大陆站点通常需 **ICP 备案**。
2. **安全组**：放行 80、443；勿对公网直接暴露 8000/5174。
3. **HTTPS**：`certbot` 或腾讯云 SSL 证书。
4. **前端构建**：生产默认 `VITE_API_BASE=/api`（同域），无需改 CORS（Core API 当前未开跨域，应同域反代）。
5. **仅家里 WSL、无公网 IP**：域名无法直接指到本机；需 CVM + 部署，或临时用 `scripts/run-public-wsl.sh`（localhost.run，**不能**绑自有域名）。

`uvicorn` 常驻示例、`nginx` 片段与 npm 排错见 `subprojects/README.md`（部署小节可随子项目文档继续补充）。

---



## 依赖说明

- **WSL** `tenclip` **环境**：以你机器上已安装版本为准（Python 3.12 + torch cu130 等可与仓库 `requirements-*.txt` 略有出入，以能跑通自检为准）。
- **新环境从零创建**：仍可用仓库内 `environment.yml`（面向通用 Conda；WSL 同样适用）：
  ```bash
  conda env create -f environment.yml
  conda env update -f environment.yml --prune
  ```
- 根目录 `requirements.txt` / `requirements-llm.txt` / `requirements-llm-lf.txt` 用于对齐依赖意图；**开发以 WSL** `tenclip` **为真源**。
- **Core API 子项目**：`requirements-subproject-core-api.txt`（与主 `requirements.txt` 分离，见 `subprojects/README.md`）。
- **前端**：`web/package.json`、`admin/package.json`（Node **>= 18**）。

---



## 备选：Windows 批处理

若临时在 Windows 上跑：可使用 `run.bat`、`setup-conda-env.bat`、`download-vlm-conda.bat` 等。**不作为本项目推荐开发方式。**

---



## 使用说明

1. **视频剪辑**：上传 → 起止秒数 → 下载。
2. **网球动作分析**：上传 → 显存模式 → **可选提示词档位**（主站 Gradio「分析提示词」Radio，或 Mobile 静态页上的 chip）→ **开始分析**。界面/API 传入的档位会**覆盖**环境变量 `TENCLIP_PROMPT_PROFILE`（未选或未传时仍用环境变量默认）。
3. **网坛新闻（Gradio）**：访问 `/news`（随 `app.py` 启动），设置偏好标签后浏览双列图文流并回传反馈。
4. **用户站（子项目）**：`web/` 开发服首页展示新闻、比赛与小红书 explore 卡片；需先启动 Core API（见上文「子项目快速启动」）。
5. **击球片段提取（长视频）**：Gradio 标签页「击球片段提取（去等待）」或 CLI `scripts/extract_stroke_clips.py` — 基于画面运动 + 击球声剪掉等待/非击球时间（200MB+ 长视频流式处理）；可选 VLM 二次过滤。

可选：复制 `env.example` 为 `.env`（需 `python-dotenv`，已在 `requirements.txt`）。

---



## 网坛新闻执行方案（评估 + 落地）



### 需求评估（你给的思路）

- **前端形态**：双列下滑图文流非常适合网坛资讯消费，优先做 H5 独立页，减少对当前 Gradio 主流程干扰。
- **内容池**：`SQLite` 作为第一阶段非常合适（轻量、零运维、本机可跑）；单机 10~50 万条新闻都可承载，后续再迁移到 MySQL/PostgreSQL。
- **推荐系统**：你提的 CF 是正确方向，但冷启动会明显（新用户/新内容稀疏）；第一阶段建议先“**内容召回 + 轻量排序**”，第二阶段再叠 CF。



### 当前已落地（MVP）

- 新增 `services/news_feed.py`：
  - 抓取来源清单见 `**config/news_sources.json`**（可增删、`enabled` 开关、`quality_tier`、HTML `parser`）；也可用环境变量 `TENCLIP_NEWS_SOURCES_CONFIG` 指向自定义路径
  - `news_feed.db`（`data/news_feed.db`）建表：`news_articles` / `news_feedback` / `news_user_profile`
  - 多源抓取入库（RSS + 站点 HTML 抓取；支持 URL 去重更新）
  - 标签抽取（球员、发球/反拍、场地等关键词）
  - 推荐排序：`新鲜度（主） + 标签匹配 + 来源质量 + 反馈热度`
- 新增 API：
  - `POST /api/news/ingest`：抓取入库
  - `GET /api/news/feed`：按 user_id/tags 分页推荐
  - `GET /api/news/tags`：热门标签
  - `POST /api/news/profile`：保存用户偏好标签
  - `POST /api/news/feedback`：记录点击/点赞/不感兴趣
- 新增页面：
  - `pages/news_page/`*，入口* `/news`*，静态资源* `/news-assets/`
  - 双列下滑、无限滚动、热门标签点击补全、卡片点击反馈回传
  - 三按钮反馈：收藏 / 已读 / 不感兴趣



### 手动跑通链路（抓取 → SQLite → 前端）

不依赖 cron，按顺序执行即可验收：

1. **抓取入库**（写入 `data/news_feed.db`）：

```bash
conda activate tenclip
cd ~/code/tenclip
python scripts/news_ingest_once.py --limit-per-source 30
```

终端应打印一行 JSON（含 `inserted_or_updated`、`sources`、`failed`，以及 `http_timeout_sec` / `source_timeout_sec`）。每个来源若在 `source_timeout_sec` 内仍未完成抓取+解析，会**自动放弃该来源**并继续下一个，避免整条任务被单个站点拖死。详细日志写入 `data/news_ingest_last_run.log`；若进程异常退出，栈在 `data/news_ingest_last_error.txt`。

1. **启动 Web**（默认端口见 `app.py`，一般为 `7861`）：

```bash
python app.py
```

1. **打开 H5**：浏览器访问 `http://127.0.0.1:7861/news`
  若首屏偏空，可点页面上的 **「抓取最新」**（等价于 `POST /api/news/ingest`），或回到第 1 步再跑一次脚本。
2. **可选自检 API**：

```bash
curl -s "http://127.0.0.1:7861/api/news/feed?limit=5" | head
```



### 第二批来源与质量分层（已执行）

- 已加入第二批中文来源：`ThePaper Sports`（澎湃「运动家」移动端列表 `m.thepaper.cn/list_25599`，HTML 抓取；避免使用 PC 栏目 CSR 页导致抓不到列表）
- 推荐排序新增来源分层加权（`source_tier`）：
  - `3` = 官方机构（ATP/WTA）
  - `2` = 主流媒体（BBC/ESPN/澎湃）
  - `1` = 聚合或其它来源
- 在“优先时效”的前提下，来源质量分仅作为次级加分，不会压过新鲜度。



### 推荐算法路线（建议）

1. **现在（已做）**：内容召回 + 规则排序（可解释、稳定、低复杂度）
2. **下一步**：隐式反馈 CF（点击/停留/点赞矩阵，ALS 或 item-based）
3. **再下一步**：混排（CF 分 + 内容相关分 + 时效分）+ 探索机制



### 需要你拍板的点（请直接选）

1. **抓取频率**：✅ 每天 4 次（建议在 `00:00 / 06:00 / 12:00 / 18:00` 执行抓取任务）
2. **来源策略**：先走 RSS 白名单（见下）再扩展站点深爬
3. **推荐目标**：✅ 优先时效（排序中时效权重高于标签权重）
4. **反馈行为**：✅ 三按钮：收藏 / 已读 / 不感兴趣



### RSS 白名单是什么？

RSS 白名单 = **一组你明确允许抓取的来源清单**（按源域名 + RSS 链接维护），例如：

- `feeds.bbci.co.uk` 的网球头条 RSS（替代已下线的 Reuters 公共 RSS）
- `www.atptour.com` 官方新闻 RSS
- `www.wtatennis.com` 官方新闻 RSS
- `www.espn.com` 网球 RSS

为什么先做白名单：

- 法务与合规更可控（只抓公开订阅流，不先做侵入式爬虫）
- 结构稳定，维护成本低（优先保证每天稳定更新）
- 便于后续扩展（再按你确认的站点逐个接入“正文解析抓取”）

当前默认来源（与 `config/news_sources.json` 同步；后续以配置文件为准）：

- **CNN · Sport（RSS）**：`http://rss.cnn.com/rss/edition_sport.rss`（推荐；含标题/摘要/链接，常带缩略图；比直接爬 `edition.cnn.com/sport` 前端页稳定）
- **Tennis.com · All news（HTML）**：`https://www.tennis.com/news/all-news/`（`parser: tennis_com_list`）
- ATP（官方）
- WTA（官方）
- BBC Sport · Tennis
- Google News · Tennis（聚合兜底，tier 较低）
- ESPN Tennis
- ThePaper Sports（移动端列表页 HTML 抓取方式接入）



### 调度建议（每天 4 次）

- 开发机先用手动触发：`POST /api/news/ingest`
- 生产/常驻环境建议由系统定时器触发（Linux cron 示例）：

```bash
0 0,6,12,18 * * * curl -X POST http://127.0.0.1:7861/api/news/ingest
```

仓库已提供可直接安装的脚本（推荐）：

```bash
cd ~/code/tenclip
chmod +x scripts/install_news_cron.sh
bash scripts/install_news_cron.sh
```

脚本会自动：

- 在 `tenclip` conda 环境下执行 `scripts/news_ingest_once.py`
- 安装每天 `00:00 / 06:00 / 12:00 / 18:00` 的 cron 任务
- 输出日志到 `data/logs/news_ingest.log`

手动验证单次抓取：

```bash
conda activate tenclip
python scripts/news_ingest_once.py --limit-per-source 30
```

卸载定时任务（仅移除新闻抓取，不影响其它 cron）：

```bash
cd ~/code/tenclip
chmod +x scripts/uninstall_news_cron.sh
bash scripts/uninstall_news_cron.sh
```

重装流程：

```bash
bash scripts/uninstall_news_cron.sh
bash scripts/install_news_cron.sh
```



## Qwen2-VL-2B 优化方案（Prompt / SFT / DPO）

基于LLaMA-Factory 工作流，把优化拆成三层：**先 Prompt 微调（零训练成本）→ 再 SFT（监督学习）→ 最后 DPO（偏好对齐）**。

### 1) Prompt 微调（最快，先做）

适用场景：你想先快速改变输出风格、结构化程度和保守性，不改模型权重。  
已实现能力（代码已接入）：

- `services/vlm_tennis.py` 支持多档提示词 profile：
  - `default`：当前通用教练风格
  - `compact`：短答 + 清单
  - `step_by_step`：按“观察-机制-纠正步骤-拍摄建议”结构输出
  - `motion_deep`：**深度动作分析**（时间分段、证据绑定到帧序、机制解释、5 日可执行处方；提示内显式**去冗余/反套话**，减轻小模型在少帧下的机械排比）
- **ArXiv 相关工作提要（Video-LLM / 时序与幻觉）**：工程上常用的「帧序证据绑定、显式不确定性」与近年论文结论方向一致，便于把 `motion_deep` 的设计放在文献脉络里理解（非穷举）：
  - **VidHalluc**（[arXiv:2412.03735](https://arxiv.org/abs/2412.03735)）：构建评测集衡量视频中**动作、时序、场景转换**等维度的幻觉，说明稀疏采样或弱对齐下模型容易编造未发生片段。
  - **Grounded-VideoLLM**（[arXiv:2410.03290](https://arxiv.org/abs/2410.03290)）：通过更细的时间表示与跨帧关系建模，强化**细粒度 temporal grounding**。
  - **Relaxing Anchor-Frame Dominance for Mitigating Hallucinations in Video LLMs**（[arXiv:2604.12582](https://arxiv.org/abs/2604.12582)）：分析 decoder 对少数「锚帧」过度注意与幻觉的关系，并提出**无额外训练**的证据再平衡思路。
- 切换方式：**Gradio 主站 /** `pages/video_input` **页的「分析提示词」Radio**，或 **Mobile 静态页**上分析卡片内的 chip；**REST** `POST /api/mobile/analyze-video` 表单字段 `prompt_profile`（与上述 key 一致）。以上均优先于环境变量；仍可用 `.env` 设全局默认：

```bash
export TENCLIP_PROMPT_PROFILE=step_by_step
export TENCLIP_PROMPT_APPEND="优先指出1个最关键风险，并给出一周训练计划。"
bash run-wsl.sh
```

建议做法：

1. 在相同视频集上做 A/B（`default` vs `compact` vs `step_by_step`）
2. 用固定评估表（可执行性、清晰度、幻觉率、长度）打分
3. 把最优 profile 作为 SFT 数据标注风格



### 2) SFT（监督微调）

目标：把“好回答风格”固化到模型参数里，提升稳定性与一致性。  
已补配置（LLaMA-Factory）：

- `configs/train/qwen2_vl_2b_qlora_sft.yaml`
- `data/dataset_info.json` 新增 `mock_tennis_qwen2_vl_sft_10k`

运行示例：

```bash
conda activate tenclip
llamafactory-cli train configs/train/qwen2_vl_2b_qlora_sft.yaml
```

当前仓库已补一版**多模态 mock 数据流**（图像路径占位，用于先打通）：

- 生成脚本：`scripts/generate_mock_vlm_datasets.py`
- 生成文件：
  - `data/mock_tennis_qwen2_vl_mm_sft_1k.json`
  - `data/mock_tennis_qwen2_vl_mm_dpo_1k.json`
- 数据注册：`data/dataset_info.json`
- 多模态训练配置：
  - `configs/train/qwen2_vl_2b_qlora_sft_mm.yaml`
  - `configs/train/qwen2_vl_2b_lora_dpo_mm.yaml`

先生成 mock 多模态数据：

```bash
conda activate tenclip
python scripts/generate_mock_vlm_datasets.py --output-dir data --count 1000
```

再按数据里的 `images` 路径批量生成占位图（用于端到端冒烟）：

```bash
conda activate tenclip
python scripts/materialize_mock_vlm_images.py --data-dir data --size 512
```

再跑多模态 SFT：

```bash
conda activate tenclip
llamafactory-cli train configs/train/qwen2_vl_2b_qlora_sft_mm.yaml
```

> 注意：脚本默认写入 `mock_images/...` 的占位图像路径。真实训练时，请用你的视频抽帧路径替换，或把真实图片按该路径结构落盘。



#### 用真实视频抽帧生成多模态数据（推荐）

当你开始积累真实训练样本时，建议用与线上推理一致的抽帧策略来落盘图片，并把图片相对路径写入数据集。

> **关键：先切片再造样本。** `build_vlm_dataset_from_videos.py` 对单个 `video_path` **整段均匀抽 N 帧**。若直接喂一整场比赛，4 帧会稀疏到无意义。应先把比赛切成「单拍 / 单回合」短片（3~10 秒），每个短片一条样本。

**步骤 0 — 比赛切片（新增脚本** `scripts/slice_match_to_clips.py`**）**：按「切片表」批量 ffmpeg 切片，并直接生成下一步要用的 manifest 骨架。切片表 JSONL 每行 `id/start/end`（时间支持 `秒` 或 `HH:MM:SS`）+ 可选标注字段；CSV 亦可（表头含 `id,start,end`）。

```bash
conda activate tenclip
# 先 --dry-run 只看将执行的 ffmpeg 命令与 manifest 预览，不落盘
python scripts/slice_match_to_clips.py --video data/matches/match.mp4 \
  --segments data/segments.jsonl --clips-dir data/clips \
  --manifest-out data/manifest_sft.jsonl --mode sft --dry-run

# 确认无误后去掉 --dry-run 实际切片（默认重编码保证精度；加 --copy 走快速不重编码）
python scripts/slice_match_to_clips.py --video data/matches/match.mp4 \
  --segments data/segments.jsonl --clips-dir data/clips \
  --manifest-out data/manifest_sft.jsonl --mode sft
```

**步骤 1 — 写 / 校验 manifest**：`scripts/build_vlm_dataset_from_videos.py`  
输入是一个 JSONL 清单（每行一个样本），最小字段示例（SFT）：

```json
{"id":"sft-0001","video_path":"/abs/path/a.mp4","instruction":"请基于图像序列分析正手稳定性","input":"场景：...","output":"..."}
```

DPO 样本示例：

```json
{"id":"dpo-0001","video_path":"/abs/path/a.mp4","instruction":"...","input":"...","chosen":"...","rejected":"..."}
```

**步骤 2 — 生成数据集**（会把抽帧 jpg 写到 `data/vlm_images/<id>/frame_*.jpg`，并在数据里写入相对路径）。加 `--register-key` 会**自动写入** `data/dataset_info.json`（与 LLaMA-Factory 的 `dataset:` 名称一致）：

```bash
conda activate tenclip
# 先校验试跑：检查 video_path 是否存在、必填字段是否齐全、预览首条样本（不抽帧、不写盘）
python scripts/build_vlm_dataset_from_videos.py --mode sft --manifest data/manifest_sft.jsonl --out data/tennis_vlm_sft.json --dry-run
# 也可只处理前 N 条：--limit 5

python scripts/build_vlm_dataset_from_videos.py --mode sft --manifest data/manifest_sft.jsonl --out data/tennis_vlm_sft.json --register-key tennis_vlm_sft
```

生成 DPO 数据集（同样可注册）：

```bash
conda activate tenclip
python scripts/build_vlm_dataset_from_videos.py --mode dpo --manifest data/manifest_dpo.jsonl --out data/tennis_vlm_dpo.json --register-key tennis_vlm_dpo
```

可选：`--dataset-info path/to/dataset_info.json` 指定非默认的 dataset 注册文件。

注册完成后，在训练 YAML 里把 `dataset:` 改成上述 key（例如 `tennis_vlm_sft`），并保持 `template: qwen2_vl`（Qwen3-VL 用 `qwen3_vl`）。

#### 击球片段提取（去等待 / 长视频）

从整段比赛视频中**自动剪掉等待、换边、捡球等非击球时间**，只保留击球/回合画面。  
**不是**全片 VLM 理解（太慢），而是 **ffmpeg 流式分析 + 启发式信号**；可选 **VLM 二次过滤** 去掉误检。

##### 实现方案


| 层级  | 模块                                | 作用                                                                                |
| --- | --------------------------------- | --------------------------------------------------------------------------------- |
| 检测  | `services/stroke_detect.py`       | 画面运动（降采样灰度帧差分）+ 击球声（流式 PCM 能量峰）→ 合并时间段                                            |
| 精修  | `services/stroke_vlm_filter.py`   | （可选）每段抽 2 帧，Qwen2-VL 判断是否在比赛/击球回合                                                 |
| 导出  | `export_stroke_clips()`           | 分段 **H.264 + yuv420p + faststart** 再拼接；**iPhone MOV/HEVC 自动重编码**（避免 Windows 无法播放） |
| CLI | `scripts/extract_stroke_clips.py` | 命令行：分析 / 导出 / 报告 / 切片表                                                            |
| UI  | Gradio **「击球片段提取（去等待）」**          | 上传长视频 → 下载击球集锦                                                                    |
| 小程序 | `miniprogram/`                    | 微信小程序：**击球剪辑** + **动作分析**（见上文「微信小程序启动」）                                           |


**长视频（200MB+）**：画面与音频均为 ffmpeg **管道流式**处理，不整段载入内存；导出后用 **ffprobe 校验**，损坏文件会直接报错。

**局限**：换边走动、鼓掌、镜头推拉可能误检/漏检；可调 `--motion-percentile` 或 `--vlm-filter`。

##### 用法

```bash
# 1) 只分析时间段（推荐先跑）
python scripts/extract_stroke_clips.py /path/to/match.MOV --analyze-only \
  --report-out data/stroke_report.json \
  --segments-out data/match_segments.jsonl

# 2) 导出击球集锦（WSL 写 Windows 路径用 /mnt/c/...）
python scripts/extract_stroke_clips.py /mnt/c/Users/you/Pictures/match.MOV \
  --out /mnt/c/Users/you/Pictures/match_strokes_only.mp4

# 3) 可选 VLM 二次过滤（更准、更慢，需 GPU + 模型）
python scripts/extract_stroke_clips.py match.MOV --vlm-filter --out out.mp4
```

**调参**：检不全 → `--motion-percentile 65`；误保留等待 → `78` 或 `--vlm-filter`。  
**勿对 MOV 使用** `--copy`（易剪坏/无法播放）。

Gradio：`bash run-wsl.sh` → 标签页 **「击球片段提取（去等待）」**。  
微信小程序：见上文 **「微信小程序启动」** 与 `miniprogram/README.md`。

##### 接入训练流水线

```bash
# 切片表 → 独立短片 + manifest
python scripts/slice_match_to_clips.py --video match.MOV \
  --segments data/match_segments.jsonl --clips-dir data/clips \
  --manifest-out data/manifest_sft.jsonl --mode sft

# 抽帧 → 多模态 SFT 数据集
python scripts/build_vlm_dataset_from_videos.py --mode sft \
  --manifest data/manifest_sft.jsonl --out data/tennis_vlm_sft.json \
  --register-key tennis_vlm_sft
```



##### 故障排查


| 现象                         | 处理                                                     |
| -------------------------- | ------------------------------------------------------ |
| 导出 MP4 无法播放（尤其 iPhone MOV） | 已默认重编码；删旧文件后重新导出，**不要** `--copy`                       |
| `IsADirectoryError: '.'`   | `--segments-out` 须为**文件路径**，如 `data/segments.jsonl`    |
| 保留比例过低/过高                  | 调整 `--motion-percentile`（默认 72）或 `--merge-gap`（默认 2.8） |




#### 改动总结（模型训练相关）

- **新增模型升级配置**：`configs/train/qwen3_vl_2b_qlora_sft_mm.yaml`、`qwen3_vl_2b_lora_dpo_mm.yaml`（多模态主线升级，模板 `qwen3_vl`，本机可 QLoRA）；`configs/train/qwen3_5_4b_qlora_sft.yaml`、`qwen3_5_4b_lora_dpo.yaml`（文本附录线，模板 `qwen3_5`，可替代 DeepSeek-7B）。DPO 配置默认开 4bit 以适配低显存。
- **新增切片脚本** `scripts/slice_match_to_clips.py`：把比赛长视频按切片表批量 ffmpeg 切成单拍/回合短片，并生成 manifest 骨架；支持 `--dry-run`、`--limit`、`--copy`。
- `scripts/build_vlm_dataset_from_videos.py` **增强**：新增 `--dry-run`（校验 `video_path` 存在与必填字段、预览首条样本，不抽帧/不写盘）与 `--limit`（只处理前 N 条）。
- **新增击球片段提取**：`services/stroke_detect.py`、`services/stroke_vlm_filter.py`、`scripts/extract_stroke_clips.py`；Gradio 标签页「击球片段提取（去等待）」；长视频流式检测 + MOV/HEVC 兼容导出。
- **关于 Qwen3.6**：实为 27B/35B 纯文本大模型，模态与体量都不适配 6GB 本机与视频主线，故不纳入；视频线升级走 `Qwen3-VL`。



### 3) DPO（偏好优化）

目标：在已有 SFT 基础上，把“更优回答 > 较差回答”的偏好进一步对齐。  
已补配置（LLaMA-Factory）：

- `configs/train/qwen2_vl_2b_lora_dpo.yaml`
- `data/dataset_info.json` 新增 `mock_tennis_qwen2_vl_dpo_10k`

运行示例：

```bash
conda activate tenclip
llamafactory-cli train configs/train/qwen2_vl_2b_lora_dpo.yaml
```

多模态 DPO 可用：

```bash
conda activate tenclip
llamafactory-cli train configs/train/qwen2_vl_2b_lora_dpo_mm.yaml
```

推荐流程：

1. 先跑 SFT 得到 adapter（`saves/qwen2_vl_2b/lora/sft`）
2. 用线上/离线评测选出 bad case，构造 chosen/rejected 对
3. 再跑 DPO，观察“建议可执行性”和“错误建议率”变化



### 数据与工程建议（落地优先级）

- **优先级 A：Prompt 评测闭环**（1-2 天就能看到收益）
- **优先级 B：SFT 数据升级到多模态**（帧采样策略与前端分析一致）
- **优先级 C：DPO 难例集**（重点覆盖逆光、远景、遮挡、低帧率）
- 每轮训练都保留评测切分，避免只看训练损失

---



## 本地测试

```bash
conda activate tenclip
python test_trim2.py
```

---



## 项目结构（节选）

```text
tenclip/
├─ app.py                      # Gradio 主应用 + /news H5
├─ run-wsl.sh                  # WSL 启动 Gradio（conda tenclip）
├─ download-vlm-conda.sh
├─ env.example
├─ requirements*.txt
├─ requirements-subproject-core-api.txt
├─ subprojects/
│   ├─ README.md               # Core API / web / admin / xhs_note 说明
│   ├─ core_api/               # FastAPI（app, models, xhs_preview, xhs_note_routes）
│   └─ xhs_note/               # 按笔记 ID + Cookie 抓取（新）
├─ web/                        # 用户站（Vite + React）
├─ admin/                      # 管理后台
├─ configs/                    # LLaMA-Factory 训练配置
├─ config/                     # 网坛 RSS 来源 news_sources.json
├─ data/                       # SQLite、Cookie、抓取日志（多数已 gitignore）
├─ model/                      # VLM 权重（见 model/README.md）
├─ services/
│   ├─ vlm_tennis.py           # VLM 抽帧与动作分析
│   ├─ stroke_detect.py        # 击球/回合时间段检测 + 导出
│   └─ stroke_vlm_filter.py    # 可选 VLM 二次过滤
├─ scripts/
│   ├─ extract_stroke_clips.py # 击球片段提取 CLI
│   ├─ slice_match_to_clips.py
│   ├─ build_vlm_dataset_from_videos.py
│   ├─ xhs_note_fetch.py
│   └─ ...
└─ test_*.py
```

---



## GitHub

示例：`https://github.com/mathslingo/tenclip`

---



## 附录 A：可选文本模型（DeepSeek 7B + LLaMA-Factory）

与**网球视频主线独立**：仓库内另有 DeepSeek 蒸馏 7B 的下载脚本与推理 YAML，供本地文本/对话实验。网球场 **VLM 默认仍为 Qwen2-VL-2B**。

- 下载：`scripts/download_llm_weights.py`，`download-deepseek-conda.bat`（Windows）
- 配置：`configs/inference/deepseek_r1_7b.yaml`
- 6GB 显存上 7B 建议量化；详见原脚本注释

在 WSL 中若需对等流程，可自行：

```bash
conda activate tenclip
python scripts/download_llm_weights.py
# 再按 configs 使用 llamafactory-cli chat ...
```

（后续若统一 WSL 脚本，可在阶段 4 补 `download-deepseek-wsl.sh`。）

---



## 附录 B：Prompt 工程论文趋势（2024-2026）

结合当前项目瓶颈（小模型在视频动作分析里容易“浅结论 + 冗余重复”），我们参考了近年多模态与 Video-LLM 的实证趋势，形成如下工程结论：

1. **小模型（<4B）并不总是“多想就更好”**
  在多模态任务上，长链 CoT / ToT 这类“重推理提示”对小模型常见副作用：输出更长但错误未减少，甚至幻觉和重复上升。  
   代表性参考：
  - Qwen2-VL 系列论文（[arXiv:2409.12191](https://arxiv.org/abs/2409.12191)）
  - R1-Zero-like 视觉推理工作（[arXiv:2504.00883](https://arxiv.org/abs/2504.00883)）
  - 多模态 Prompt 评测（[arXiv:2504.10179](https://arxiv.org/abs/2504.10179)）
2. **“证据先行”的结构化输出比“自由思考”更稳**
  对视频任务，先强制输出“可核对证据（帧段 + 事实）”，再引用证据给结论，通常能降低时间幻觉与凭空补全。  
   相关方向：
  - Grounded-VideoLLM（[arXiv:2410.03290](https://arxiv.org/abs/2410.03290)）
  - VidHal（[arXiv:2411.16771](https://arxiv.org/abs/2411.16771)）
  - VidHalluc（[arXiv:2412.03735](https://arxiv.org/abs/2412.03735)）
  - TimeRefine（[arXiv:2412.09601](https://arxiv.org/abs/2412.09601)）
3. **“限额深度”比“无限展开”更适合 2B 级模型**
  对 2B 级模型，给出每节条目上限、固定格式和证据引用约束，通常比开放式深度提示更能提高信息密度与可读性。



### 已落地到本项目的策略

- 新增提示词档位：`step_by_step_v2`（证据驱动双阶段）
  - 阶段A：证据提取（证据表）
  - 阶段B：引用证据ID做机制分析、优先级和 3 天微周期训练处方
  - 强约束：去重复、禁第一人称、限条数、限总字数、禁止新增“无证据硬事实”

推荐在 6GB 显存 + `Qwen2-VL-2B` 场景优先使用该档位，并与 `step_by_step` / `motion_deep` 做 A/B 评测。