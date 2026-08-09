# 小程序「图文双列 Feed」改造方案

> 文档：`docs/feed_tab_construction.md`  
> 日期：2026-07-12  
> 状态：**M1 已落地（接真 Feed + 新闻库管理后台）**

---

## M0 落地清单（2026-07-12）

| 项 | 路径 |
|----|------|
| 发现双列 + 顶栏 | `miniprogram/pages/feed/` |
| 原生详情 | `miniprogram/pages/feed-detail/` |
| 我 | `miniprogram/pages/me/`（含 Mock 开关） |
| Mock 数据 | `miniprogram/utils/feed_mock.js` |
| 数据源封装 | `miniprogram/utils/feed_api.js` |
| 四 Tab | `components/bottom-tabs/` |
| 首页 | `app.json` → `pages/feed/index` |
| 开关默认 | 见 M1：`FEED_USE_MOCK = false` |

Build tag（M0）：`2026-07-12-feed-m0`

---

## M1 落地清单（2026-07-12）

| 项 | 说明 |
|----|------|
| 小程序默认真源 | `FEED_USE_MOCK = false`；失败回退 Mock；空库显示空态 |
| 顶栏赛事/教学 | API 数据按标题/tags 启发式 `inferChannel` |
| 新闻库管理后台 | `https://clip.uchanceai.com/admin/news-feed`（本机 `:7861/admin/news-feed`） |
| 管理 API | `GET /api/news/admin/overview`、`/articles`、`/ingest-runs`、`/queues` |
| 抓取任务落库 | 表 `news_ingest_runs`；点后台「立即抓取」或 `POST /api/news/ingest` |
| 类目分布 | **Mock 比例**（`categories_is_mock: true`）；来源分布为真实聚合 |

Build tag（M1）：`2026-07-12-feed-m1`

后台页面：`pages/news_admin/`（轻量 HTML，不依赖 React `admin/` CMS）。

---

当前小程序底部原有两页（击球剪辑、动作分析）。本次大幅调整：

1. **新增小红书风格双列下滑图文笔记页**（瀑布流 Feed）
2. Feed 内容为 **网球新闻 / 图文笔记**（先 mock，再接爬取→库→展示）
3. **大模型分析** 作为独立 Tab 上架（复用现有页）
4. 增加 **「我」** 个人入口

品牌：**UChance**（导航栏、关于页统一使用）。

---

## 1. 仓库里已有、可复用的能力

| 能力 | 位置 |
|------|------|
| 抓取 + SQLite | `services/news_feed.py`，`data/news_feed.db` |
| 来源配置 | `config/news_sources.json` |
| API | `GET /api/news/feed` 等 |
| H5 双列对照 | `pages/news_page/` → `/news` |
| 动作分析页 | `miniprogram/pages/action-analyze/`（已对接 API） |

Mock 用于前端并行；后端主链路已通。

---

## 2. 已确认信息架构

### 2.1 底部 Tab（四栏）

```
[ 发现 ]  [ 剪辑 ]  [ 分析 ]  [ 我 ]
（默认首页 = 发现）
```

| Tab | 路由 |
|-----|------|
| 发现 | `pages/feed/index` |
| 剪辑 | `pages/stroke-extract/` |
| 分析 | `pages/action-analyze/` |
| 我 | `pages/me/index` |

### 2.2 Feed 顶栏（Mock 过滤）

| 顶栏 | Mock 规则 |
|------|-----------|
| 推荐 | 全部 |
| 赛事 | `channel === '赛事'` |
| 教学 | `channel === '教学'` |

### 2.3 卡片与详情

- 列表：封面 + 标题 + 作者行 + 点赞（小红书式）
- 点击 → 原生详情 `pages/feed-detail/`
- 封面失败 → 本地 / 色块 fallback（不做图床代理）

---

## 3. 分阶段

### M0（已完成）

四 Tab + Feed 双列 + 顶栏 Mock + 详情 + `FEED_USE_MOCK` 开关。

### M1（已完成）

`FEED_USE_MOCK=false` 接 `/api/news/feed`；新闻库 HTML 管理后台；ingest 任务落库；类目分布暂 mock。

### M2+

反馈埋点、封面图代理、正式类目标注、推荐；分析 UX 见 §11。

---

## 7. 已确认决策（2026-07-12）

| 项 | 选择 |
|----|------|
| D1 | **B** 发现 \| 剪辑 \| 分析 \| **我** |
| D2 | **A** 默认进发现 |
| D3 | **A** 原生详情 |
| D4 | **A** fallback |
| D5 | **C** Mock + 开关 |
| D6 | **B** 顶栏 + Mock 过滤 |
| D7 | 先露出分析；打磨思路 **§11**（本阶段不改分析逻辑） |
| D8 | 品牌 **UChance** |

---

## 11. 大模型分析 Tab — UX 打磨思路（D7 后续，先不实现）

本阶段仅底部露出「分析」。以下为下一轮 backlog：

### 11.1 认知与引导

- 区分：**剪辑 = 出集锦视频**；**分析 = 出文字动作指导**
- 首次进入：建议「30 秒～2 分钟清晰侧拍/正拍」
- 「我」页增加历史分析任务（需列表 API 或本地缓存 task_id）

### 11.2 选视频与上传

- 与剪辑统一选视频 + 全屏进度浮层
- 按文件大小档位提示预估耗时
- 失败态区分可重试网络错误 vs 格式/过长

### 11.3 结果呈现

- 正文分区（站位 / 挥拍 / 练习建议）
- 「复制全文」置顶；「再分析一次」保留参数
- 运行环境信息默认折叠

### 11.4 性能模式

- 默认省显存；质量优先加「更慢」提示
- 体验版可只留「标准 / 分步」prompt，减少选择

### 11.5 与 Feed 联动（可选）

- 教学笔记详情 CTA：「用自己的视频做 AI 分析」
- 避免在资讯流硬插广告式入口

---

## 10. 下一步

1. ~~确认 D1–D8~~ ✅  
2. ~~实现 M0~~ ✅  
3. ~~实现 M1（真 Feed + 管理后台）~~ ✅  
4. 云主机：`git pull` + 重启 `tenclip-uchanceai`，打开 `/admin/news-feed` 点「立即抓取」  
5. 小程序重编译（Build `2026-07-12-feed-m1`），确认发现页走新闻库  
6. M2：类目真实化、反馈埋点、封面治理  

同步微信开发者工具（WSL → Windows NTFS）：见 [`docs/miniprogram-windows-sync.md`](miniprogram-windows-sync.md)，脚本 `scripts/sync-miniprogram-to-windows.sh`。
