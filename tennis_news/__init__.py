"""tennis_news：live-tennis.cn 网球新闻抓取 → 本地存储 → 小程序双列前端。

- live_tennis.py: 抓取 + 解析首页动态流（纯标准库）
- store.py:       JSON 快照 + upsert 到 news_feed.db（复用既有 schema）
- ingest.py:      CLI 编排（python -m tennis_news.ingest）
"""
from __future__ import annotations

from tennis_news.live_tennis import (
    HOME_URL,
    SOURCE_NAME,
    fetch_home,
    parse_home_items,
)
from tennis_news.store import save_snapshot, upsert_rows

__all__ = [
    "HOME_URL",
    "SOURCE_NAME",
    "fetch_home",
    "parse_home_items",
    "save_snapshot",
    "upsert_rows",
]
