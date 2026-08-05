# TenClip 子项目说明

本目录存放与主仓库 **Gradio 视频 Demo** 解耦的独立工程，拥有单独的依赖与运行方式，默认不并入根目录 `requirements.txt`。

包含 **Core API**（`core_api/`）、**VLM API**（`vlm_api/`，本地大模型 HTTP 服务）、**小红书抓取模块**（`xhs_note/`，与 `core_api` 内旧版 `xhs_preview` 路由并存）。配套前端在仓库根目录 **`web/`**、**`admin/`**。

---

## VLM API（本地大模型 HTTP 服务）

独立 FastAPI，复用 `services/vlm_tennis.py` 的 Qwen2-VL 推理，供动作分析、击球 VLM 过滤等模块通过 HTTP 调用（默认 **7862**，与主 `app.py` **7861** 错开）。

```bash
cd ~/code/tenclip
# 需已安装 requirements-llm-lf.txt 或 requirements-llm.txt
pip install -r requirements-vlm-api.txt   # 首次
bash scripts/start_vlm_api.sh
```

- 文档：`http://127.0.0.1:7862/docs`
- 健康检查：`GET /v1/health`
- 网球视频分析：`POST /v1/analyze/video`（multipart 上传）
- 服务器已有视频：`POST /v1/analyze/video/path`（路径须在 `data/` 下）
- 多图对话：`POST /v1/chat`（JSON + `images_base64`）

可选环境变量：`TENCLIP_VLM_API_KEY`（设置后请求须带 `X-API-Key`）、`TENCLIP_VLM_API_WORKERS`（GPU 建议 `1`）。

Python 调用示例：`python -m subprojects.vlm_api.client_example /path/to/video.mp4`

---

## 快速启动（最少步骤）

在 **WSL** 中打开仓库根目录（路径形如 `~/code/tenclip`，不要用 Windows 通过 `\\wsl.localhost\...` 跑 npm）。准备 **两个终端**：

**终端 1 — Core API（必须先起）**

```bash
cd ~/code/tenclip
conda activate tenclip   # 若用 conda；否则用你已配好的 Python 环境
pip install -r requirements-subproject-core-api.txt   # 首次或依赖变更后
python3 -m uvicorn subprojects.core_api.app:app --host 127.0.0.1 --port 8000
```

看到类似 `Uvicorn running on http://127.0.0.1:8000` 即就绪。接口文档：`http://127.0.0.1:8000/docs`。

**终端 2 — 用户站（可选，与 API 联调）**

```bash
cd ~/code/tenclip/web
# Node 需 >= 18，且 which npm 不能是 /mnt/c/...（详见下文「npm」小节）
npm install   # 首次
npm run dev -- --host 0.0.0.0
```

浏览器打开终端里提示的地址（一般为 **http://127.0.0.1:5174**）。前端通过 **`/api` 代理** 访问本机 **8000** 端口上的 Core API。

**管理后台（可选）**：另开终端 `cd ~/code/tenclip/admin && npm install && npm run dev`（默认 **5173**）。

**一键脚本（可选）**：`bash scripts/start_core_api.sh`、`bash scripts/start_web.sh`（若遇 CRLF 报错见下文「CRLF」小节）。

**自检**：`python3 scripts/verify_core_api.py`（建表、`/health`、注册/登录及列表接口抽样）。

---

## Core API（`core_api/`）

### 组成模块

| 文件 / 包 | 说明 |
|-----------|------|
| `app.py` | FastAPI 应用：路由、`News` / `Player` / `Match` / `Video` / `User` 的 CRUD；`GET /videos` 支持 **`match_id`**；`GET /news` 支持 **`player_id`**（按球员姓名匹配正文/摘要等）；`GET /matches` 支持 **`player_id`**（任一侧上场） |
| `models.py` | SQLAlchemy ORM 模型（表名带 `api_` 前缀）；`News` 含 `body` / `tags` / `players`（详情与标签展示，SQLite 启动时自动 `ALTER` 补齐列） |
| `db.py` | 数据库 URL、`engine`、`SessionLocal`、依赖注入用 `get_db` |
| `security.py` | 密码哈希（bcrypt）、JWT 签发与校验 |
| `deps.py` | `get_current_user` 等依赖（如 `Authorization: Bearer`） |
| `redis_cache.py` | 可选 Redis：`hot_news` 键、`/news/hot` 缓存与新闻变更失效 |

### 依赖安装

在仓库根目录执行（建议使用独立 venv / conda 环境，避免与主项目冲突）：

```bash
cd /path/to/tenclip
pip install -r requirements-subproject-core-api.txt
```

依赖清单见仓库根目录 **`requirements-subproject-core-api.txt`**（FastAPI、Uvicorn、SQLAlchemy、Passlib、python-jose、Redis 客户端等）。

### 启动服务

仓库根目录下：

```bash
uvicorn subprojects.core_api.app:app --host 127.0.0.1 --port 8000
```

也可一键安装依赖并启动（仓库根目录，`chmod +x` 后执行）：

```bash
bash scripts/start_core_api.sh
```

浏览器或 HTTP 客户端访问：

- 健康检查：`GET http://127.0.0.1:8000/health`
- OpenAPI 文档：`http://127.0.0.1:8000/docs`（若未在生产环境关闭）

### 环境变量

| 变量 | 说明 |
|------|------|
| `TENCLIP_CORE_API_DATABASE_URL` | 数据库连接串；未设置时使用仓库内 SQLite：`data/core_api.db`（相对路径由 `db.py` 解析） |
| `TENCLIP_CORE_API_REDIS_URL` / `REDIS_URL` | 若配置且可连接，则启用 `/news/hot` 的 Redis 缓存（键 `hot_news`，TTL 5 分钟）；未配置则每次读库 |
| `TENCLIP_XHS_COOKIE` | 小红书：**`xhs_note` 模块必需**；旧版 `xhs_preview` 在无 Cookie 时仍可尝试 meta。粘贴浏览器 Cookie 串 `a1=…;web_session=…` |
| `TENCLIP_XHS_COOKIE_FILE` | （可选）Cookie 文件路径；未设置时若存在 `data/xhs_cookie.txt` 则自动读取（已 .gitignore） |
| `TENCLIP_XHS_NO_COOKIE` | 设为 `1` / `true` 时忽略 Cookie（脚本 `fetch_xhs_notes_to_db.py` 会默认设置，便于无登录态校验） |

小红书笔记元数据（标题、简介、封面、`#话题`）：`GET /utils/xhs-note-preview?url=…`；批量并行：`POST /utils/xhs-note-previews`，JSON body 如 `{ "note_ids": ["24位hex", "…"], "urls": ["https://www.xiaohongshu.com/explore/…"] }`，`note_ids` 与 `urls` 可混用，合计不超过 24 条。

**从搜索词拉 id 再拉 meta**：`GET /utils/xhs-search-note-ids?keyword=网球&limit=24`（等价于站内 `search_result?keyword=…&source=web_explore_feed&type=51`），返回 `{ "note_ids", "search_url" }`；一步完成搜索页解析 + 笔记预览：`GET /utils/xhs-search-previews?keyword=网球&preview_limit=12`，返回 `{ "items", "note_ids", "search_url" }`（`items` 与批量预览结构相同）。也可用 `search_url=` 传入完整搜索 URL（须为 `/search_result` 路径）。

离线校验并入库后，可用 **`GET /utils/xhs-cached-notes?limit=50`** 读取已写入的 `api_xhs_notes`（按 `fetched_at` 倒序）。

### 小红书笔记抓取（`xhs_note/`，独立于 `xhs_preview`）

新模块 **`subprojects/xhs_note/`**：按 **24 位笔记 ID** + **登录 Cookie** 拉取 explore 页，优先解析内嵌 JSON（`__INITIAL_STATE__` / 按 `note_id` 锚定），避免旧版仅靠 `og:title` 时四条笔记标题相同的问题。Cookie 约定与上表相同（`data/xhs_cookie.txt`、`TENCLIP_XHS_COOKIE`、`TENCLIP_XHS_COOKIE_FILE`）。

**Python 调用**：

```python
from subprojects.xhs_note import fetch_note_by_id
note = fetch_note_by_id("69dd7f1d000000001b022940")
print(note.title, note.image_url)
```

**CLI**（仓库根目录）：

```bash
python3 scripts/xhs_note_fetch.py 69dd7f1d000000001b022940
python3 scripts/xhs_note_fetch.py --ids-file data/xhs_notes.csv --json-out data/xhs_note_fetched.json
```

**HTTP**（Core API 已注册，与 `xhs_preview` 路由并存）：`GET /utils/xhs-note-by-id?note_id=24位hex` 或 `/api/utils/xhs-note-by-id?note_id=…`，返回 `note_id`、`title`、`description`、`image_url`、`tags` 等。

### 数据与运维相关脚本（仓库根目录）

| 脚本 | 作用 |
|------|------|
| `scripts/start_core_api.sh` | 安装 Core API 依赖并启动 Uvicorn（`127.0.0.1:8000`） |
| `scripts/start_web.sh` | 安装 `web/` 依赖并启动 Vite 开发服务 |
| `scripts/verify_core_api.py` | 校验依赖、建表、`/health` 与注册/登录流程 |
| `scripts/fetch_xhs_notes_to_db.py` | 按 explore URL 无 Cookie 抓取笔记标题/正文摘要/封面并打印；`--commit` 写入 `api_xhs_notes` |
| `scripts/run_xhs_demo_cache.py` | 一键：打印四条首页 Demo → 入库 → 查 `api_xhs_notes`（仓库根执行 `python3 scripts/run_xhs_demo_cache.py`，避免 `.sh` 在 Windows 下 CRLF 导致 bash 报错） |
| `scripts/xhs_note_fetch.py` | 使用 **`xhs_note`** 模块按 ID 抓取（需 Cookie）；支持 `--ids-file`、`--json-out` |
| `scripts/import_core_api_json.py` | 从 JSON 批量导入球员、比赛、新闻（可选视频），支持 `--dry-run` |

### 配套前端（仓库根目录，非本目录内）

与 Core API 联调时，可并行启动：

| 目录 | 说明 | 开发命令（示例） |
|------|------|------------------|
| `admin/` | 管理后台（Ant Design）：列表与表单 CRUD | `npm install && npm run dev`（默认端口见该目录 `vite.config.ts`） |
| `web/` | 用户端站点（Ant Design）：首页新闻与比赛等 | `bash scripts/start_web.sh` 或 `cd web && npm install && npm run dev` |

上述前端开发服务器通常将 **`/api` 代理到 `http://127.0.0.1:8000`**；生产环境请通过反向代理或 `VITE_API_BASE` 指向真实 API 地址。

### 生产部署（腾讯云域名 · 摘要）

1. **DNS**：在 DNSPod 将域名 **A 记录** 指到 CVM 公网 IP；放行安全组 **80/443**。
2. **构建前端**：`cd web && npm ci && npm run build`（`admin/` 同理）；生产保持 `VITE_API_BASE=/api`（默认）即可同域访问 API。
3. **Nginx**：静态托管 `web/dist`；`location /api/ { proxy_pass http://127.0.0.1:8000/; }`（路径规则与 `web/vite.config.ts` 一致）。
4. **API 进程**：`uvicorn subprojects.core_api.app:app --host 127.0.0.1 --port 8000`（勿对公网裸奔 8000）；生产设置 `TENCLIP_CORE_API_JWT_SECRET`。
5. **仅本机 WSL、无公网**：需买 CVM 部署，或使用仓库根目录 `scripts/run-public-wsl.sh` 临时隧道（不能绑自有域名）。

更完整的 Gradio / 新闻 / VLM 说明见仓库根目录 **`readme.md`**（含路线图与环境变量表）。

### 说明

- Core API 与主项目 `app.py`（Gradio）**未自动挂载**；需单独进程运行 Uvicorn。
- 业务错误体格式由 `app.py` 中间件统一包装为 JSON（含 `ok`、`error` 等字段），前端需按该格式解析或使用已封装的 HTTP 客户端。

### 常见问题（WSL / Bash 与 CRLF）

若运行 `scripts/start_web.sh` 等出现 **`set: invalid option`**、路径中出现 **`$'\r'`**、或 **`npm` 去找仓库根的 `package.json`**，多半是文件被保存成了 **CRLF**。

**预防（推荐）**：根目录 **`.editorconfig`** 已规定 **LF**；请在 Cursor / VS Code 中启用 EditorConfig 插件（内置或扩展），并避免把「行尾」改成 CRLF。Git 侧由 **`.gitattributes`** 在检出时尽量统一为 LF。

**一次性修复已有文件**：

```bash
sed -i 's/\r$//' scripts/start_web.sh scripts/start_core_api.sh
```

从远端克隆后若历史提交里混了 CRLF，可尝试：

```bash
git add --renormalize .
git status   # 确认变更后再提交
```

也可不用脚本，直接：

```bash
cd ~/code/tenclip/web && npm install && npm run dev -- --host 127.0.0.1
```

### 常见问题（npm：Windows Node + WSL 目录）

若 **`npm install`** 出现 **`EPERM`**、**`esbuild` 的 `install.js` 失败**、日志里出现 **`\\wsl.localhost\...`** 或 **UNC 路径不支持**，说明在用 **Windows 上的 Node/npm** 操作 **WSL 文件系统**（通过 `\\wsl.localhost\...` 打开的工程）。**CMD 不能把工作目录设在 UNC 上**，原生模块安装常会失败。

**正确做法**：在 **WSL Ubuntu 终端**里使用 **Linux 的 `node` / `npm`**（路径应在 Linux 侧，例如 `~/code/tenclip/web`）：

```bash
cd ~/code/tenclip/web
which npm          # 应为 WSL 内路径，勿用 /mnt/c/... 下的 Windows npm 去装 WSL 目录
node -v
# 若上次安装半失败，可先清理再装：
# rm -rf node_modules package-lock.json
npm install && npm run dev -- --host 0.0.0.0
```

**`which npm` 指向 `/mnt/c/Program Files/...` 时**：仍是 **Windows 的 npm**（WSL 会把 Windows 的 `PATH` 拼进来，且常排在前面）。请改用 **Linux 侧 Node 20+**（推荐 [nvm](https://github.com/nvm-sh/nvm)），并确认：

```bash
which node   # 应在 $HOME/.nvm/... 或 /usr/bin，且 node -v >= 18
which npm    # 必须与 node 同属一套，不能是 /mnt/c/...
```

示例（**nvm**，装好后 `which npm` 应在 `~/.nvm/...`，且 **Node ≥ 18**）：

```bash
# 若 raw.githubusercontent.com 超时，优先试 jsDelivr：
curl -o- https://cdn.jsdelivr.net/gh/nvm-sh/nvm@v0.40.1/install.sh | bash
# 仍失败：用浏览器能打开的镜像站下载 install.sh 到本机后执行 bash install.sh，或改用下方 snap

source ~/.bashrc   # 或重开终端
# 在国内拉 Node 二进制可设镜像后再 install（可选）：
export NVM_NODEJS_ORG_MIRROR=https://npmmirror.com/mirrors/node
nvm install 20
nvm use 20
cd ~/code/tenclip/web && npm install
```

**不装 nvm 的替代**：若 `snap` 可用：

```bash
sudo snap install node --classic --channel=22/stable
```

装好后若 **`node -v` 仍是 12.x**、**`which node` 仍是 `/usr/bin/node`**，或 **`which npm` 仍是 `/mnt/c/...`**，说明 **PATH 先命中了 apt 旧包或 Windows**。按顺序处理：

1. **让 snap 优先**（当前终端立刻验证）：

```bash
export PATH="/snap/bin:$PATH"
hash -r
which node    # 期望 /snap/bin/node
which npm     # 期望 /snap/bin/npm
node -v
```

确认无误后，把 **`export PATH="/snap/bin:$PATH"`** 写进 **`~/.bashrc`**（放在文件靠后、conda 初始化之前或之后试一次，保证最终 `which` 正确）。

2. **去掉 apt 自带的旧 Node**（避免和 `/usr/bin/node` 抢 `node` 命令；按需执行）：

```bash
sudo apt remove --purge -y nodejs npm
hash -r
which node
```

3. 若 **`which npm` 仍是 Windows 路径**：说明 WSL 把 Windows 的 `PATH` 拼进来了且排在前面。可在 **`/etc/wsl.conf`** 中关闭拼接（**会影响**在 WSL 里直接调用部分 Windows 命令的便利度）：

```ini
[interop]
appendWindowsPath=false
```

在 Windows 里执行 **`wsl --shutdown`** 后重开 WSL 生效。若不想改全局，务必保证 **`/snap/bin` 在 `PATH` 最前**，且本机存在 **`/snap/bin/npm`**（`ls /snap/bin/npm`）。

Ubuntu 自带的 **`/usr/bin/node` 常为 12.x**，对 **Vite 5** 过旧；`web/`、`admin/` 已声明 **`engines.node >= 18`**，请用 nvm / snap 等升级到 **18 或 20+ LTS**，不要仅 `apt install nodejs` 凑合。

在 Cursor 中建议 **用 WSL 打开仓库**，终端用 **bash（WSL）**。

### 常见问题（`npm install` 很慢、终端几乎没输出）

npm 默认可能较安静；要看**解析依赖、下载、执行脚本**的过程，可加大日志级别：

```bash
npm install --loglevel verbose
# 更啰嗦：npm install --loglevel silly
```

若希望安装生命周期脚本（如 `postinstall`）的输出直接打在终端上：

```bash
npm install --foreground-scripts --loglevel verbose
```

在国内访问 **registry.npmjs.org** 常偏慢，可改用镜像（仅影响当前用户，可随时改回）：

```bash
npm config set registry https://registry.npmmirror.com
npm install --loglevel verbose
# 恢复官方：npm config delete registry
```

---

## 后续扩展

若在 `subprojects/` 下新增其它子项目，建议在本文件增加一节：**名称、用途、安装与启动命令、与主仓库的关系**，便于统一查阅。
