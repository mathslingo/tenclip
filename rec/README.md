# 新闻推荐子系统（`rec/`）

> 从 `services/news_feed.py` 拆出的 M0 规则推荐；抓取/入库仍在 `services/news_feed.py`。

## 布局

```text
rec/
  __init__.py      # 对外 API
  recommend.py     # RecommendInput + recommend_news（按 score 倒排）
  richness.py      # 图文丰富度特征
  profile.py       # 用户兴趣标签
  feedback.py      # 点击/点赞等反馈 → popularity
  tags.py          # TAG_KEYWORDS / suggest_tags / split_tags_csv
  timeutil.py      # UTC 工具
```

## 用法

```pytho n
from rec import RecommendInput, recommend_news, record_feedback, suggest_tags

items = recommend_news(RecommendInput(user_tags=[], limit=20))
```

HTTP：`GET /api/news/feed`（`app.py` 已改为 `from rec import …`）。

兼容：`from services.news_feed import recommend_news` 仍可用（re-export）。

## 打分（M0）

`score = richness + 0.45*freshness + 20*tag_overlap + 4*source_tier + popularity`

- 有真实封面 `+80`，无图 `-12`
- 占位标题（如「澎湃新闻 · 文章 xxx」）`-30`

设计演进见 `docs/recsys-m1-design.md` / `docs/recsys-realtime-roadmap.md`。
