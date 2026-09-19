# 网球新闻：定时抓取 → SQLite → 小程序发现页

> 更新日期：2026-09-18。评估全文见 [news_ingest_optimization.md](news_ingest_optimization.md)。

## 执行计划（已同意落地）

跨配置、入库逻辑和宿主机调度，分步如下。

| 阶段 | 做什么 | 验收 |
| --- | --- | --- |
| **P0a 源清单** | 海外源（BBC/ATP/WTA/ESPN/Tennis.com/Google）默认 `enabled=false`；保留 Live Tennis CN + 澎湃 | 单次 ingest 不再空等 6 个超时源 |
| **P0b 澎湃** | 只抓运动家体育列表；**网球标题排前**，其它体育仍入库；丢掉占位标题 | 发现页网球在前，篮球足球可垫后 |
| **P0c upsert** | 标题/摘要/图未变则 **不刷新** `ingested_at` / `published_at`；run 记录区分 inserted / updated / unchanged | 推荐新鲜度不再被重复抓取刷歪 |
| **P0d 熔断** | 表 `news_source_circuit`：连续失败 ≥5 则跳过 6 小时 | 偶发失败不拖死后续 run |
| **P0e 健康** | `/api/mobile/health` 增加 `news_last_ingest_at`、`news_articles`、`news_ingest_stale` | 停更一眼能看出来 |
| **P0f 调度** | **crontab 每 2 小时**（`0 */2 * * *` 调 `news_ingest_once.py`）；与 systemd timer **二选一**，勿双开 | `crontab -l` 能看到任务；health 不过期 |
| **P1 补图** | 新文无封面时最多抓 5 条详情 `og:image`（短超时） | 无图率下降，不拖垮整次 ingest |

**不在本次做：** 海外代理、无头浏览器打 ATP、迁 MySQL、把 ingest 拆成独立长期进程。

**频率：** 默认 2 小时。勿再装 `*/30` 空转。本地仍可用 `TENCLIP_NEWS_HOURLY_INGEST=1`（间隔默认 3600s，可 `TENCLIP_NEWS_INGEST_INTERVAL_SEC`）。

生产调度：**crontab**（2026-09-19 起）。systemd timer 单元仍留在 `scripts/deploy/` 作备选，本机已 `disable`，避免和 cron 双跑。

---

## 现状（已具备）

| 能力 | 实现 |
|------|------|
| 抓取 | `services/news_feed.py` → `ingest_news()` |
| 来源 | `config/news_sources.json`：**默认只开** Live Tennis CN + 澎湃运动家（体育入库、网球置顶）；海外源 `enabled=false` |
| 存储 | SQLite `data/news_feed.db` 表 `news_articles`（唯一键 `url`，可重复抓取更新） |
| 推荐目录 | `data/rec_notes.db` 表 `rec_notes`：用户笔记+资讯，统一 10 位 `note_id`（见 [unified_rec_notes.md](unified_rec_notes.md)） |
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

## 2. 定时任务（生产：crontab 每 2 小时）

默认抓 `config/news_sources.json` **已启用**源（国内：Live Tennis CN、澎湃运动家）→ `data/news_feed.db`。海外源默认关闭。

### 方式 A：crontab（本机生产）

```bash
bash scripts/install_news_cron.sh
crontab -l | grep news_ingest
```

默认：`0 */2 * * *`（0/2/4… 点）。日志：`data/logs/news_ingest.log`。  
改周期：`NEWS_CRON_SCHEDULE='0 * * * *' bash scripts/install_news_cron.sh`

HTTP 调已运行的 API（可选）：

```bash
TENCLIP_NEWS_INGEST_URL=http://127.0.0.1:7861 bash scripts/install_news_cron_http.sh
```

卸载：`bash scripts/uninstall_news_cron.sh`

### 方式 B：systemd timer（备选，勿与 cron 同时开）

```bash
sudo cp scripts/deploy/tenclip-news-ingest.service /etc/systemd/system/
sudo cp scripts/deploy/tenclip-news-ingest.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tenclip-news-ingest.timer
```

切到 cron 时先停 timer：`sudo systemctl disable --now tenclip-news-ingest.timer`

---

## 3. 小程序展示真新闻

1. `miniprogram/utils/config.js`：`FEED_USE_MOCK = false`（已默认）
2. 本地调试：`LOCAL_DEV = true`，`LOCAL_API_HOST` 指向本机/WSL
3. 微信开发者工具勾选不校验合法域名
4. 「我」页确认 Mock 关闭；发现页底部应显示「数据源：新闻库 · 本机库」
5. **发现页排序**：默认按 `published_at` **时间倒序**（最新在前）；笔记与资讯混排。`recommend_news()` 仍保留作后续算法实验。
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

- 国内 ECS 默认只抓可达源；ATP 等 403 的源保持 `enabled=false`，有出口再开
- 部署后 `bash scripts/install_news_cron.sh`，并确认 `systemctl disable --now tenclip-news-ingest.timer`（避免双跑）
- health：`curl -s http://127.0.0.1:7861/api/mobile/health` 看 `news_last_ingest_at` / `news_ingest_stale`
