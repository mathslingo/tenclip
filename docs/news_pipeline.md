# 网球新闻：定时抓取 → SQLite → 小程序发现页

> 更新日期：2026-07-18

## 现状（已具备）

| 能力 | 实现 |
|------|------|
| 抓取 | `services/news_feed.py` → `ingest_news()` |
| 来源 | `config/news_sources.json`（含 **ATP**、**WTA**、BBC、ESPN、Tennis.com、澎湃、**Live Tennis CN** 等） |
| 存储 | SQLite `data/news_feed.db` 表 `news_articles`（唯一键 `url`，可重复抓取更新） |
| 任务记录 | 表 `news_ingest_runs` |
| API | `POST /api/news/ingest`，`GET /api/news/feed` |
| 管理后台 | `/admin/news-feed` |
| 小程序 | `FEED_USE_MOCK=false`，发现页请求真 Feed；失败回退 Mock |

后续可迁 MySQL：只需替换 `news_feed.py` 里 SQLite 访问层，表结构可先对齐再迁。

---

## 1. 本地立刻试抓

```bash
cd ~/code/tenclip
# 启动 API（另开终端）
GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh

# 单次抓取（推荐）
~/miniconda3/envs/tenclip/bin/python scripts/news_ingest_once.py --limit-per-source 20

# 或 HTTP
curl -s -X POST 'http://127.0.0.1:7861/api/news/ingest?limit_per_source=20'
```

看结果：

```bash
curl -s 'http://127.0.0.1:7861/api/news/feed?limit=5'
# 浏览器打开
# http://127.0.0.1:7861/admin/news-feed
```

进程内每小时（可选，适合本地不想配 cron）：

```bash
TENCLIP_NEWS_HOURLY_INGEST=1 GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh
```

---

## 2. 安装「每 30 分钟」定时任务

抓取 `config/news_sources.json` 已启用源（含 Live Tennis CN）→ `data/news_feed.db`。

### 方式 A：直接跑 Python（需 conda `tenclip`）

```bash
bash scripts/install_news_cron.sh
crontab -l | grep news_ingest
```

默认：`*/30 * * * *`（每 30 分钟）。日志：`data/logs/news_ingest.log`。  
改周期：`NEWS_CRON_SCHEDULE='0 * * * *' bash scripts/install_news_cron.sh`

### 方式 B：HTTP 调已运行的服务（云主机常用）

API 常驻（如 `tenclip-uchanceai` 监听 7862）时：

```bash
TENCLIP_NEWS_INGEST_URL=http://127.0.0.1:7862 bash scripts/install_news_cron_http.sh
```

卸载：

```bash
bash scripts/uninstall_news_cron.sh
```

---

## 3. 小程序展示真新闻

1. `miniprogram/utils/config.js`：`FEED_USE_MOCK = false`（已默认）
2. 本地调试：`LOCAL_DEV = true`，`LOCAL_API_HOST` 指向本机/WSL
3. 微信开发者工具勾选不校验合法域名
4. 「我」页确认 Mock 关闭；发现页底部应显示「数据源：新闻库 · 本机库」
5. **推荐排序**：`rec.recommend_news()` 对有封面、有效标题/摘要的条目加权，按 `score` 倒排；占位标题（如「澎湃新闻 · 文章 xxx」）降权
6. **无图 mock**：客户端对空 `image_url` 按 id 稳定轮换网球主题 Unsplash 封面；加载失败同样回退 mock 图

推荐代码目录：`rec/`（见 `rec/README.md`）。

Build tag：`2026-07-22-rec-richness-mock`

---

## 3.5 Live Tennis CN（网球之家中文站）

中文源 `https://www.live-tennis.cn/zh/home` 的首页动态流（球员夺冠 / 排名里程碑），
抓取与解析封装在独立包 **`tennis_news/`**：

| 文件 | 职责 |
|------|------|
| `tennis_news/live_tennis.py` | 抓取首页 + 解析 `cHomeWheelDesc` 卡片（纯标准库，不依赖 services） |
| `tennis_news/store.py` | JSON 快照落盘（`data/live_tennis_probe/`）+ upsert 到 `news_feed.db` |
| `tennis_news/ingest.py` | CLI 编排：fetch → parse → 存储 |

两种使用方式（结果都进同一张 `news_articles`，小程序双列发现页自动显示）：

```bash
cd ~/code/tenclip

# 方式一：独立抓 Live Tennis（含 JSON 快照，便于离线复现）
~/miniconda3/envs/tenclip/bin/python -m tennis_news.ingest --cap 60
# 离线解析已保存的 HTML（不联网）：
~/miniconda3/envs/tenclip/bin/python -m tennis_news.ingest --from-file data/live_tennis_probe/latest_home.html

# 方式二：随主管线一起抓（config 已注册 parser=live_tennis_list）
~/miniconda3/envs/tenclip/bin/python scripts/news_ingest_once.py --limit-per-source 30
```

解析要点：
- 卡片结构 `cHomeWheelDescText`（标题）+ `cHomeWheelDescDot`（日期 + 赛事/地点）。
- 封面：取同张 `swiper-slide` 的 `data-background`（`static.live-tennis.cn/images/trophies/…`），过滤生日占位图。
- 过滤「生日快乐」等非新闻卡；去除站点 iconfont 私有区字形。
- 首页各条无独立详情页，用 `#lt-<sha1(标题)>` 作为唯一 URL，适配 `news_articles.UNIQUE(url)`。
- 标签：统一 `赛事`，另按内容追加 `冠军` / `排名`。

---

## 4. ATP / WTA 标签

入库时根据来源与标题自动打标签：`ATP` / `WTA` / `赛事` / `教学` 等。  
小程序卡片左上角会显示 ATP / WTA 角标；顶栏「赛事」按 channel 过滤。

---

## 5. 云主机注意

- 安全组/防火墙不影响出站抓取 RSS
- 部分站点（ATP）可能 403，ingest 会记入 `failed`，其它源继续
- 部署后执行一次 `install_news_cron_http.sh`，并在后台点一次「立即抓取」验证
