"""TenClip 新闻推荐子系统（M0 规则精排）。

对外入口见 ``rec`` 包根：``recommend_news`` / ``RecommendInput`` /
``record_feedback`` / ``set_user_profile`` / ``suggest_tags``。

后续 M1（向量召回 / LightGBM）可在此包内扩展，见 docs/recsys-m1-design.md。
"""
from __future__ import annotations

from rec.catalog import backfill_rec_catalog, init_rec_catalog, list_rec_notes
from rec.feedback import record_feedback
from rec.profile import get_user_profile_tags, set_user_profile
from rec.recommend import RecommendInput, home_feed, recommend_news
from rec.tags import TAG_KEYWORDS, split_tags_csv, suggest_tags

__all__ = [
    "TAG_KEYWORDS",
    "RecommendInput",
    "backfill_rec_catalog",
    "get_user_profile_tags",
    "home_feed",
    "init_rec_catalog",
    "list_rec_notes",
    "record_feedback",
    "recommend_news",
    "set_user_profile",
    "split_tags_csv",
    "suggest_tags",
]
