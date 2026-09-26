"""M0 规则推荐：图文丰富度 + 时效 + 标签 + 来源质量 + 热度，按 score 倒排。"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rec.profile import get_user_profile_tags
from rec.richness import content_richness
from rec.tags import split_tags_csv, title_looks_like_tennis
from rec.timeutil import utc_now


@dataclass
class RecommendInput:
    user_tags: list[str]
    limit: int = 20
    offset: int = 0
    user_id: str | None = None


def _published_ts(item: dict[str, Any]) -> float:
    raw = item.get("published_at") or item.get("created_at") or 0
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        v = float(raw)
        if v > 1e12:
            return v / 1000.0
        if v > 1e8:
            return v
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def _news_row_item(r: sqlite3.Row) -> dict[str, Any]:
    art_tags = split_tags_csv(r["tags_csv"])
    item = dict(r)
    item["kind"] = "news"
    item["tags"] = art_tags
    from services.poster import attach_poster

    return attach_poster(
        item,
        kind="news",
        item_id=str(item.get("id") or ""),
        title=str(item.get("title") or ""),
    )


def list_news_by_time(*, limit: int = 60, offset: int = 0) -> list[dict[str, Any]]:
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, source, source_domain, source_tier, title, summary, url,
                   image_url, tags_csv, published_at, popularity
            FROM news_articles
            ORDER BY datetime(published_at) DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [_news_row_item(r) for r in rows]


def home_feed(*, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """发现页默认：用户笔记 + 资讯按 published_at 时间倒序。"""
    from services.social import list_notes

    limit = max(1, min(int(limit), 60))
    offset = max(0, int(offset))
    news = list_news_by_time(limit=400, offset=0)
    notes = list_notes(limit=80, offset=0)
    merged = news + notes
    merged.sort(key=_published_ts, reverse=True)
    page = merged[offset : offset + limit]
    for it in page:
        it["score"] = round(_published_ts(it), 3)
    return page


def recommend_news(inp: RecommendInput) -> list[dict[str, Any]]:
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    limit = max(1, min(inp.limit, 60))
    offset = max(0, inp.offset)

    tags = sorted({x.strip() for x in inp.user_tags if x and x.strip()})
    if not tags and inp.user_id:
        tags = get_user_profile_tags(inp.user_id)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, source, source_domain, source_tier, title, summary, url,
                   image_url, tags_csv, published_at, popularity
            FROM news_articles
            ORDER BY datetime(published_at) DESC
            LIMIT 400
            """
        ).fetchall()

    now = utc_now()
    scored: list[tuple[int, float, dict[str, Any]]] = []
    for r in rows:
        art_tags = split_tags_csv(r["tags_csv"])
        tag_overlap = len(set(tags) & set(art_tags))
        try:
            pub = datetime.fromisoformat(r["published_at"])
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (now - pub).total_seconds() / 3600.0)
        except Exception:
            age_hours = 72.0
        # 基础推荐：图文丰富度优先，其次时效 / 标签 / 来源质量 / 热度
        richness = content_richness(r["title"] or "", r["summary"] or "", r["image_url"])
        freshness = max(0.0, 120.0 - min(age_hours * 2.0, 120.0))
        source_bonus = max(0.0, min(float(r["source_tier"] or 1), 3.0)) * 4.0
        score = (
            richness
            + freshness * 0.45  # 时效次要，避免「刚入库无图」压过「有图旧闻」
            + tag_overlap * 20.0
            + source_bonus
            + float(r["popularity"] or 0.0)
        )
        item = dict(r)
        item["tags"] = art_tags
        from services.poster import attach_poster

        attach_poster(
            item,
            kind="news",
            item_id=str(item.get("id") or ""),
            title=str(item.get("title") or ""),
        )
        item["score"] = round(score, 2)
        item["richness"] = round(richness, 2)
        tennis_first = 1 if (
            title_looks_like_tennis(r["title"] or "") or "网球" in art_tags
        ) else 0
        scored.append((tennis_first, score, item))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [it for _, _, it in scored[offset : offset + limit]]
