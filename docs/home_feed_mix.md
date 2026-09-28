# 首页笔记混排

> 2026-09-29。本文是**推荐首页（发现页「推荐」）**的混排设计。  
> M0 已接入 `home_feed()` / `GET /api/news/feed`。向量召回（M1）尚未做。  
> 统一 item 目录见 [unified_rec_notes.md](unified_rec_notes.md)。资讯侧向量方案见 [recsys-m1-design.md](recsys-m1-design.md)。

## 1. 要解决的问题

发现页「推荐」现在把 `news_articles` 和用户笔记按 `published_at` 倒序拼在一起。教学稿（`source_domain=tenclip.coach`）发布时间被故意放在新闻之前，只在客户端拉较大一页时附带返回，所以推荐流里几乎看不到教学。

用户笔记很少（个位数），新闻每两小时一批。纯按时间排，首页会被澎湃体育占满，教学和球友笔记露不出头。

混排目标：

| 目标 | 做法 |
| --- | --- |
| 三类都出现 | 固定槽位，不让全局分数把某一类挤光 |
| 新闻仍是主体 | 每 6 张卡片里新闻占 4 张 |
| 球友内容可见 | 有新笔记时每页留 1 个用户槽 |
| 教学可回访 | 每页留 1 个教学槽，不要求它比新闻新 |
| 网球优先 | 只在新闻槽内部把网球标题排在其他体育前面 |
| 可解释、可降级 | 第一版用规则分；日志够了再换成学习排序 |

「赛事」「教学」两个顶栏仍是**过滤**，不走这套混排。混排只服务「推荐」。

## 2. 三类内容

候选统一读 `rec_notes`（10 位 `note_id`）。业务库仍各自为源，混排不直接扫两张业务表。

| 车道 `lane` | 判定 | 源 |
| --- | --- | --- |
| `news` | `source_kind=news`，且不是教学 | `news_feed.db` / `news_articles`。Live Tennis、澎湃运动家 |
| `coach` | `source_domain=tenclip.coach`，或标签含「教学」 | `scripts/seed_coach_articles.py` 写入的 10 篇图文 |
| `user_note` | `source_kind=user_note` 且 `status=active` | `social.db` / `notes` |

教学稿在目录里的 `source_kind` 仍是 `news`，车道用 `extra_json.source_domain` 或标签拆开，避免再加一种 `source_kind`。

不进候选：

- `status=deleted`
- 标题匹配占位「澎湃新闻 · 文章 {id}」
- 无标题且无正文的用户笔记

## 3. 模型

两段式：**车道内打分**，再 **槽位混排**。不把三类丢进一个分数里比大小。新闻时效半衰期短，和教学、笔记比绝对分，教学和笔记会稳定输。

```text
rec_notes (active)
    │  按 lane 拆开
    ├─ news      ─ score_news      ─ 网球优先的有序列表
    ├─ coach     ─ score_coach     ─ 教学有序列表
    └─ user_note ─ score_user      ─ 笔记有序列表
              │
              ▼
        槽位模板（每 6 张一轮）
              │
              ▼
        缺槽回填 → 去重 → 分页
```

### 3.1 特征

| 特征 | 含义 | 来源 |
| --- | --- | --- |
| `age_hours` | 距 `published_at` 的小时数 | 目录时间 |
| `richness` | 已有 `content_richness()`：真封面、标题长度、摘要长度；占位标题扣分 | `rec/richness.py` |
| `tennis` | 标题像网球，或标签含「网球」 | `title_looks_like_tennis` |
| `tier` | `source_tier`，1–3 | 新闻源配置 |
| `pop` | `popularity`（点击、赞、收藏累加，现有反馈） | `news_feedback` / 社交计数 |
| `tag_overlap` | 与用户兴趣标签的交集个数 | `news_user_profile.tags_json`；无用户则为 0 |
| `has_image` | 有 `http` 封面，或已生成的大字报路径 | `image_url` |

大字报封面算「有图」，但 `richness` 里真封面仍只给 `http` 加分。混排不另造一套丰富度。

### 3.2 车道内分数

新鲜度用指数衰减，半衰期按车道不同：

```text
fresh(age, half_life) = exp(-age_hours / half_life)
```

| 车道 | 半衰期 | 理由 |
| --- | --- | --- |
| `news` | 18 小时 | 两小时一抓，一天内的稿应明显更靠前 |
| `user_note` | 36 小时 | 笔记少，新发的多留一会儿 |
| `coach` | 14 天 | 教学内容慢变，不跟新闻抢「刚刚」 |

车道内分数（第一版，手写权重）：

```text
score_news = 40*fresh_news + 0.25*richness + 25*tennis + 4*tier + 8*tag_overlap + pop
score_user = 50*fresh_user + 0.20*richness + 15*tennis + 6*tag_overlap + pop
score_coach = 20*fresh_coach + 0.15*richness + 10*tennis
```

`tennis`、`tag_overlap` 为 0/1 或小整数。`pop` 直接加，量级目前很小。

新闻车道排序键是 `(tennis 降序, score_news 降序)`，和现在 `recommend_news()` 的「网球标题优先、其余按分」一致。同一条澎湃稿的重复 URL 已在入库时按 url 唯一；若标题重复但 URL 不同，混排不去重标题，只按 `note_id` 去重。

### 3.3 槽位模板

小程序发现页一页 6 张。服务端按 6 的倍数组块，再按 `offset/limit` 切片。

每块 6 个位置：

```text
1 news → 2 news → 3 user_note → 4 news → 5 news → 6 coach
```

| 位置 | 车道 | 取该车道当前最高分，取出后指针后移 |
| --- | --- | --- |
| 1、2、4、5 | news | 新闻 |
| 3 | user_note | 用户笔记 |
| 6 | coach | 教学 |

一页 6 张的比例是新闻 4、笔记 1、教学 1。请求 `limit=20` 时连续铺开这个模板，直到凑满或候选耗尽。

缺槽回填，按这个顺序，且不重复已放入的 `note_id`：

| 缺的槽 | 回填 |
| --- | --- |
| 没有用户笔记 | 用下一条新闻；新闻也没有则用教学 |
| 没有教学 | 用下一条新闻；新闻也没有则用笔记 |
| 没有新闻 | 用笔记，再教学 |

用户笔记和教学都空时，整页退回纯新闻，行为与现在的时间流接近，但新闻槽内部仍是网球优先加分数，而不是纯时间。

### 3.4 重排约束

槽位定完后只做两条硬约束，不再按分重排整页：

1. **相邻不重复同一非新闻来源。** 连续两张不能都是同一 `user_id` 的笔记。教学同一 `note_id` 本来就不会重复。
2. **新闻来源打散。** 连续 3 张新闻里，不能 3 张都是同一个 `source`（例如三连澎湃）。若违反，在新闻车道里向后换一条不同来源的稿，换不到则保持原样。

不在混排阶段按 `published_at` 再排序。客户端若把「推荐」结果再按时间倒序排，槽位会被拆掉。接入时发现页「推荐」应信任服务端顺序；「赛事」「教学」仍可按时间排后再过滤。

### 3.5 个性化与冷启动

| 情况 | 行为 |
| --- | --- |
| 无 `user_id`、无标签 | `tag_overlap=0`，三条车道仍按模板出 |
| 只有兴趣标签 | 加在 `score_news` / `score_user` 上，不改变槽位比例 |
| 新用户没有行为 | 不查向量，不查点击 |
| 新笔记 / 新稿 | 靠 `fresh` 进入该车道前列，再由槽位决定会不会露在这一页 |
| 教学只有固定 10 篇 | 车道很短，翻页后教学槽按回填规则变成新闻 |

M1 的向量召回（见 `recsys-m1-design.md`）以后只替换**新闻车道的候选生成**：FAISS Top-K 再套上面的 `score_news`。槽位模板保持不变。用户笔记和教学量小，继续全量打分，不做 ANN。

### 3.6 以后的学习排序

有曝光和点击之后，车道内的手写分可以换成同一个线性模型或 LightGBM，特征仍是上表，另加 `lane` 的 one-hot 作为偏置，**不取消槽位**。

```text
score = w · features + b_lane
```

训练标签：`impression` 为 0，`click` / `read` 为 1，`like` / `bookmark` 为更强正样本，`dislike` 为负样本。和 M1 文档里 `news_feedback.action` 的约定相同。

槽位比例用离线统计调，不放进模型自动学。否则样本里新闻占绝对多数，模型会把比例学回「几乎全是新闻」。

## 4. 和现有接口的关系

`GET /api/news/feed` 的响应形状不变：`items[]` 里每条带 `id`、`kind`、`title`、`summary`、`image_url`、`tags`、`published_at`、`score`。

接入混排后约定：

| 字段 | 含义 |
| --- | --- |
| `kind` | 对外仍是 `news` 或 `note`。教学的 `kind` 保持 `news` |
| `lane` | 新增 `news` / `coach` / `user_note`，便于排查；旧客户端可忽略 |
| `score` | 该条在**自己车道内**的分数，不是跨车道可比的全局分 |
| `note_id` | 10 位目录 id，与业务 `id` 并存 |

`recommend_news()` 继续只排资讯，不替代首页。首页函数仍是 `home_feed()`，接入时改它的内部实现，不新开路径。

详情打开走 `GET /api/news/articles/{id}`，与混排无关。混排不改变「不在前 40 条就打不开」的修复。

## 5. 分页

模板按 6 张一块生成一条长序列（上限 120，与现在 `home_feed` 的 limit 上限一致），再 `slice(offset, offset+limit)`。

同一请求内车道指针单调前进，所以第 2 页不会重复第 1 页已经用过的 `note_id`。不做跨请求会话；用户下拉刷新会重新从各车道最高分取，这是预期行为。

## 6. 分阶段

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 现在 | 已替换。`rec/mix.py` 的 `mix_home_feed` 由 `home_feed()` 调用 | 每 6 张为新闻、新闻、笔记、新闻、新闻、教学 |
| M0 混排 | 已落地。候选读 `rec_notes`，车道内规则分 | 有笔记时第 3 张是用户笔记，第 6 张是教学 |
| 客户端 | 「推荐」不再按 `published_at` 重排 | 需发一版小程序后，手机上的顺序才跟槽位一致 |
| M1 | 新闻车道改为向量召回 + 同一套槽位 | 兴趣标签能改变新闻槽里的顺序，不改变 4:1:1 |

M0 混排和客户端改动要一起上。只改服务端、小程序仍按时间重排，首页看起来和现在一样。

## 7. 不在本文范围

- 「赛事」「教学」顶栏的过滤规则（仍由标题和标签启发式决定）
- 评论、点赞写回哪个业务表
- 四套测速页皮肤
- 用大模型生成教学稿或重写新闻标题
