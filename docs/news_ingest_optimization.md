# 资讯抓取任务评估与优化方案

> 基于 2026-09-18 本机 `data/news_feed.db`、`config/news_sources.json`、`services/news_feed.py`、systemd `tenclip-api`、crontab 的实测。  
> 管线说明仍见 [news_pipeline.md](news_pipeline.md)（含 2026-09-18 执行计划与落地）。本文回答：**现网抓取任务合不合理，以及怎么改。**

---

## 结论（先看这里）

**设计合理，现网运行不合理。**

管线本身（多源 RSS/HTML → 按 URL upsert → `news_ingest_runs` 记账 → `/api/news/feed`）适合小程序发现页这种「轻量内容池」。问题在**调度停了、海外源长期全灭、中文源未过滤、刷新过于频繁却几乎没有新文**。

| 项 | 现状 | 判定 |
| --- | --- | --- |
| 调度 | **无 crontab**；`TENCLIP_NEWS_HOURLY_INGEST` 未开；health 里 `news_hourly_ingest: false` | 不合理 |
| 最近一次成功写入 | **2026-08-18 16:01 UTC**（停更约 1 个月） | 不合理 |
| 库内文章 | 183 篇；澎湃 125 + Live Tennis CN 58 | 能撑展示，但已过期 |
| 8 个启用源 | 仅 **2 个国内源稳定成功**；BBC/Google 网络不可达，ATP 403，Tennis.com/WTA 超时，ESPN 解析空 | 配置与机房网络不匹配 |
| 历史 239 次 run | 222 次 `partial`、17 次 `failed`；末段几乎每次都是「2 成功 + 6 失败」且 `inserted_or_updated=40` | 周期过密，多为重复 upsert |
| 无封面 | 125 / 183（约 68%）无 `image_url`（澎湃解析不取图） | 发现页观感差 |
| 澎湃 | 体育频道整页抓，**未限定网球**；占位标题「澎湃新闻 · 文章 {id}」会被推荐降权 | 噪声大 |
| 推荐 | `rec.recommend_news` 规则分尚可；资讯过期后发现页主要靠 **社交笔记混排** | 产品上能刷，资讯职责空心化 |

**不建议**在不改源清单的情况下，把 30 分钟 cron 原样装回去——会继续空转海外超时、刷同一批澎湃 URL。

---

## 1. 任务设计：哪些是对的

1. **源与解析分离**：`news_sources.json` 可开关、`quality_tier` 进推荐，比写死在代码里好维护。  
2. **单源超时**（默认 HTTP 12s / 源总预算 28s）：避免一个站拖死整次 ingest。  
3. **`UNIQUE(url)` upsert**：重复抓不会炸库。  
4. **`news_ingest_runs`**：失败原因可审计（现网就是靠这个看出来「永远那 6 个源挂」）。  
5. **进程内调度可选、生产推荐独立 cron**：进程挂了任务还在，方向对。  
6. **Live Tennis CN** 独立包 + 中文首页动态：国内可达、网球相关，是目前真正有效的源。

这些不必推倒重来。

---

## 2. 现网问题拆解

### 2.1 调度真空

文档写「每 30 分钟 cron」或 `TENCLIP_NEWS_HOURLY_INGEST=1`。本机：

- `crontab -l` **没有** `news_ingest`  
- `tenclip-api.service` **没有** 该环境变量  
- 最后一次 run 的 `started_at` 停在 **8 月 18 日**（当时还是约 30 分钟一次，后改成整点，然后彻底停）

小程序 `FEED_USE_MOCK=false`，feed 仍 200，是因为库里还有旧文 + `social.py` 把笔记拼进 `/api/news/feed`。用户感知「有内容」，并不等于资讯抓取在干活。

### 2.2 源与机房不匹配（主因）

启用源 8 个，末次 run 失败形态（之后每次几乎一样）：

| 源 | 错误 | 含义 |
| --- | --- | --- |
| BBC Tennis RSS | `Network is unreachable` | 出网/IPv6/墙，不是偶发 |
| Google News RSS | `timed out` | 同上 |
| Tennis.com HTML | `source timeout (>28s)` | 慢或被拦 |
| WTA RSS | `source timeout (>28s)` | 同上 |
| ATP RSS | `HTTP 403` | 反爬，Cookie 预热不够 |
| ESPN RSS | `no rows parsed` | 结构变了或空 feed |
| 澎湃体育 HTML | 成功 | 国内，但是综合体育 |
| Live Tennis CN | 成功 | 国内、网球向 |

在国内 ECS 上把 ATP/BBC/ESPN 当默认主力，**预期成功率就不该按 8/8 来设计**。没有代理时，默认源应是「国内可达 + 网球相关」。

### 2.3 频率与「40 条更新」的错觉

SQLite `ON CONFLICT DO UPDATE` 时 `rowcount` 仍计入 `inserted_or_updated`。每次 40 ≈ 两源 × 30 上限里实际解析到的条数被**整表刷新 `ingested_at`**，不是每天 +40 篇新稿。

按 `ingested_at` 日期看，高峰一天也就十几到四十条「被摸过」的行；真正新增远小于 30 分钟一次的成本。  
海外源每次还要吃满 28s 超时，整次 run 约 **90 秒**，其中大半是注定失败的等待。

对首页列表类源：**1～2 小时一次**足够；赛事日可临时加密。30 分钟适合「比分快讯」，不适合现在这套解析。

### 2.4 内容质量

- 澎湃 `list_25599` 是体育列表，标题含足球/篮球也会进库。  
- 解析不到标题就写成「澎湃新闻 · 文章 {id}」，推荐会降权，feed 仍占坑。  
- `published_at` 对澎湃用 **抓取时刻**，时效信号被污染。  
- 无图比例高，和小程序双列卡片不匹配（客户端虽有 Unsplash 兜底，不像资讯站）。

### 2.5 运维可观测性不足

失败写进 SQLite，但没有「超过 24h 无成功 run 就告警」。调度停了一个月，health 只多了一个 `news_hourly_ingest: false`，容易漏看。

---

## 3. 优化方案（按优先级）

### P0 — 先让「该抓的」稳定跑（不改模型、改配置+调度）

1. **恢复调度，但降频**  
   推荐 **systemd timer**（与 `tenclip-api` 同机、比 crontab 好查）：每 **2 小时** 调  
   `POST http://127.0.0.1:7861/api/news/ingest?limit_per_source=20`  
   或 `python scripts/news_ingest_once.py --limit-per-source=20`。  
   不要默认 30 分钟。赛事窗口可用覆盖日历加密到 1 小时。

2. **默认源改成「国内网球」**（`news_sources.json`）  

   | 源 | 建议 |
   | --- | --- |
   | Live Tennis CN | **保持 enabled**，主力 |
   | 澎湃体育 | 保持但加 **标题关键词过滤**（网球/ATP/WTA/公开赛/大满贯等），否则降为 enabled=false |
   | BBC / Google / ESPN / ATP / WTA / Tennis.com | 默认 **enabled=false**，打标 `region=overseas`；有稳定出网或代理后再开 |

3. **熔断**  
   同一源连续失败 ≥5 次：跳过 N 小时（或自动 `enabled=false` 写回/内存标记），避免每次空等 28s。成功一次则恢复。

4. **health 暴露新鲜度**  
   `/api/mobile/health` 增加 `news_last_ingest_at`、`news_last_ok_sources`、`news_article_count`。超过 24h 无成功 run 视为降级（不必把整个 API 判死）。

5. **upsert 不刷新无变化行的 `ingested_at`**  
   标题/摘要/图都没变则不 bump，推荐里的「新鲜度」才有意义。

### P1 — 内容与解析

1. **澎湃/列表页**：关键词白名单；丢掉「澎湃新闻 · 文章 id」占位条。  
2. **补图**：对无 `image_url` 的新 URL 再请求详情页 `og:image`（限流：每源每轮最多 5 张）。  
3. **发布时间**：RSS 用 `pubDate`；HTML 能解析则用，否则宁缺勿用抓取时刻冒充。  
4. **标题近重复**：同一源 24h 内相似度过高只留一条。  
5. **中文增源（有解析再开）**：优先「网球垂直站 / 稳定 RSS」，不要再堆综合体育频道。候选需单独评估 robots 与版权，不在本文默认打开。

海外源若要重新启用：固定出口（代理）+ 加长单源超时 + ATP 保留 Cookie 预热；仍 403 就维持关闭，不要用无头浏览器硬刚（和现网 Gradio 进程抢资源）。

### P2 — 结构（需要时再做）

- 源并行（线程池，上限 3）：缩短总时长；熔断后收益更大。  
- 详情正文进 `body` 字段（库表要加列）：推荐 richness 才上得去。  
- 文章保留策略：例如 90 天或 2000 条封顶，按 `published_at` 删。  
- 独立 `tenclip-news-ingest.service`：ingest 与 API 进程分离，避免抓取超时占 worker。  
- MySQL：量级 183 条完全没必要迁；等量到万级或要多实例再迁。

---

## 4. 建议的目标态（验收）

| 指标 | 目标 |
| --- | --- |
| 调度 | systemd timer 或 cron **确实存在**且最近 24h 有 run |
| 单次 run | 默认只打 1～3 个国内源，总时长 **< 20s** |
| 状态 | 常态 `ok` 或偶发 `partial`，不再「永远 6 失败」 |
| 日新增 | 以 Live Tennis + 过滤后澎湃为准，允许几天为 0（非赛事日） |
| 无图率 | 新入库 < 30%（靠 og:image） |
| 发现页 | 资讯条目 `published_at` 中位年龄 < 7 天（有调度后） |

手工验收：

```bash
curl -s -X POST 'http://127.0.0.1:7861/api/news/ingest?limit_per_source=20'
curl -s 'http://127.0.0.1:7861/api/news/admin/ingest-runs?limit=5'
curl -s 'http://127.0.0.1:7861/api/news/feed?limit=5'
```

管理页：`/admin/news-feed`。

---

## 5. 不建议做的

- 把海外 6 源原样 30 分钟空转（费带宽、拖超时、日志刷屏）。  
- 在 `app.py` 请求线程里同步抓 8 个源且无超时（现在有超时，不要拿掉）。  
- 用无头 Chrome 抓 ATP 当默认路径。  
- 为 183 行 SQLite 上 Hadoop/MySQL。  
- 不经版权评估批量镜像全文对外。

---

## 6. 推荐落地顺序

```text
1. 改 news_sources.json 默认源 + 澎湃关键词（配置）
2. 装 2 小时一次的 systemd timer / cron（运维）
3. health 新鲜度字段 + upsert 不盲刷 ingested_at（小改代码）
4. 熔断 + og:image（中改）
5. 有出口再考虑打开 BBC/ATP
```

未执行 1～2 之前，发现页资讯部分会继续靠 **8 月库存 + 用户笔记**。这不是抓取任务「设计失败」，是 **任务停了且源清单与 ECS 网络不一致**。
