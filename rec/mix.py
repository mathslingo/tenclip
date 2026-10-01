"""发现页「推荐」混排：车道内规则分 + 每 6 张的槽位模板。

设计见 docs/home_feed_mix.md。赛事/教学顶栏不走这里。
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from rec.catalog import DB_PATH, init_rec_catalog
from rec.profile import get_user_profile_tags
from rec.richness import content_richness
from rec.tags import split_tags_csv, title_looks_like_tennis
from rec.timeutil import utc_now

_PLACEHOLDER_RE = re.compile(r"(澎湃新闻\s*[·•]?\s*文章\s*\d+)|(文章\s*\d{6,})", re.I)

SLOT = ("news", "news", "user_note", "news", "news", "coach")
FALLBACK = {
    "user_note": ("user_note", "news", "coach"),
    "coach": ("coach", "news", "user_note"),
    "news": ("news", "user_note", "coach"),
}
HALF_LIFE = {"news": 18.0, "user_note": 36.0, "coach": 24.0 * 14}
MAX_SEQ = 120


def _age_hours(published_at: str, created_at: float, now: datetime) -> float:
    raw = (published_at or "").strip()
    if raw:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (now - dt).total_seconds() / 3600.0)
        except Exception:
            pass
    try:
        created = float(created_at or 0)
    except (TypeError, ValueError):
        created = 0.0
    if created > 1e8:
        return max(0.0, (now.timestamp() - created) / 3600.0)
    return 72.0


def _lane_of(source_kind: str, source_domain: str, tags: list[str]) -> str:
    if source_kind == "user_note":
        return "user_note"
    if source_domain == "tenclip.coach" or "教学" in tags:
        return "coach"
    return "news"


def _is_tennis(title: str, tags: list[str]) -> int:
    if "网球" in tags or title_looks_like_tennis(title):
        return 1
    return 0


def _score(lane: str, fresh: float, richness: float, tennis: int, tier: float, overlap: int, pop: float) -> float:
    if lane == "news":
        return 40 * fresh + 0.25 * richness + 25 * tennis + 4 * tier + 8 * overlap + pop
    if lane == "user_note":
        return 50 * fresh + 0.20 * richness + 15 * tennis + 6 * overlap + pop
    return 20 * fresh + 0.15 * richness + 10 * tennis


def _load_candidates(user_tags: list[str]) -> dict[str, list[dict[str, Any]]]:
    init_rec_catalog()
    now = utc_now()
    tag_set = {t.strip() for t in user_tags if t and t.strip()}
    lanes: dict[str, list[dict[str, Any]]] = {"news": [], "coach": [], "user_note": []}
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM rec_notes WHERE status='active'"
        ).fetchall()
    for row in rows:
        title = (row["title"] or "").strip()
        body = (row["body"] or "").strip()
        summary = (row["summary"] or "").strip() or body
        if row["source_kind"] == "user_note" and not title and not body:
            continue
        if _PLACEHOLDER_RE.search(title):
            continue
        tags = split_tags_csv(row["tags_csv"])
        extra: dict[str, Any] = {}
        try:
            extra = json.loads(row["extra_json"] or "{}")
        except Exception:
            extra = {}
        if not isinstance(extra, dict):
            extra = {}
        domain = str(extra.get("source_domain") or "")
        lane = _lane_of(row["source_kind"], domain, tags)
        tennis = _is_tennis(title, tags)
        overlap = len(tag_set & set(tags))
        try:
            tier = float(extra.get("source_tier") or 1)
        except (TypeError, ValueError):
            tier = 1.0
        tier = max(0.0, min(tier, 3.0))
        age = _age_hours(row["published_at"], row["created_at"], now)
        fresh = math.exp(-age / HALF_LIFE[lane])
        richness = content_richness(title, summary, row["image_url"])
        pop = 0.0
        score = _score(lane, fresh, richness, tennis, tier, overlap, pop)
        item = _to_feed_item(row, extra, tags, lane, score, tennis)
        lanes[lane].append(item)
    _attach_like_counts(lanes)
    lanes["news"].sort(key=lambda it: (it["_tennis"], it["score"]), reverse=True)
    lanes["user_note"].sort(key=lambda it: it["score"], reverse=True)
    # 教学槽先用 tenclip.coach 的图文。标题里带「训练」被打上教学标签的体育稿排在它们后面。
    lanes["coach"].sort(
        key=lambda it: (1 if it.get("source_domain") == "tenclip.coach" else 0, it["score"]),
        reverse=True,
    )
    return lanes


def _to_feed_item(
    row: sqlite3.Row,
    extra: dict[str, Any],
    tags: list[str],
    lane: str,
    score: float,
    tennis: int,
) -> dict[str, Any]:
    images: list[str] = []
    try:
        parsed = json.loads(row["images_json"] or "[]")
        if isinstance(parsed, list):
            images = [str(x) for x in parsed if str(x).strip()]
    except Exception:
        images = []
    image = (row["image_url"] or "").strip() or (images[0] if images else "")
    title = (row["title"] or "").strip()
    body = (row["body"] or "").strip()
    summary = (row["summary"] or "").strip() or body
    if row["source_kind"] == "user_note":
        sid = str(row["source_ref"] or "")
        if sid.startswith("user:"):
            sid = sid.split(":", 1)[1]
        if not title:
            title = (body[:24] + "…") if len(body) > 24 else (body or "笔记")
        author = str(extra.get("author_name") or "球友")
        item = {
            "id": "note-" + sid,
            "note_id": row["note_id"],
            "kind": "note",
            "lane": lane,
            "user_id": row["user_id"] or "",
            "title": title,
            "summary": summary,
            "body": body,
            "image_url": image,
            "images": images or ([image] if image else []),
            "source": author,
            "author_name": author,
            "author_avatar": "",
            "url": row["url"] or "",
            "tags": tags or ["笔记"],
            "published_at": row["published_at"] or "",
            "popularity": 0,
            "like_count": 0,
            "score": round(score, 3),
            "_tennis": tennis,
            "_social_note_id": sid,
        }
    else:
        ref = str(row["source_ref"] or "")
        news_id: int | str = ref.split(":", 1)[1] if ref.startswith("news:") else row["note_id"]
        try:
            news_id = int(news_id)
        except (TypeError, ValueError):
            pass
        source = str(extra.get("source") or "资讯")
        item = {
            "id": news_id,
            "note_id": row["note_id"],
            "kind": "news",
            "lane": lane,
            "user_id": "",
            "title": title,
            "summary": summary,
            "body": summary,
            "image_url": image,
            "images": images or ([image] if image else []),
            "source": source,
            "author_name": source,
            "source_domain": str(extra.get("source_domain") or ""),
            "source_tier": extra.get("source_tier") or 1,
            "url": row["url"] or "",
            "tags": tags,
            "tags_csv": row["tags_csv"] or "",
            "published_at": row["published_at"] or "",
            "popularity": 0,
            "like_count": 0,
            "score": round(score, 3),
            "_tennis": tennis,
            "_news_id": news_id if isinstance(news_id, int) else None,
        }
    from services.poster import attach_poster

    attach_poster(item, kind="news" if item["kind"] == "news" else "note", item_id=str(item["id"]), title=title)
    return item


def _attach_like_counts(lanes: dict[str, list[dict[str, Any]]]) -> None:
    """把资讯 popularity 和笔记真实点赞数写回候选，供发现页展示。"""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    news_db = root / "data" / "news_feed.db"
    social_db = root / "data" / "social.db"
    news_ids: list[int] = []
    note_ids: list[str] = []
    for items in lanes.values():
        for it in items:
            nid = it.get("_news_id")
            if isinstance(nid, int):
                news_ids.append(nid)
            sid = it.get("_social_note_id")
            if sid:
                note_ids.append(str(sid))
    news_pop: dict[int, float] = {}
    if news_ids and news_db.is_file():
        try:
            with sqlite3.connect(str(news_db)) as conn:
                q = ",".join("?" * len(news_ids))
                for r in conn.execute(
                    f"SELECT id, popularity FROM news_articles WHERE id IN ({q})",
                    news_ids,
                ):
                    try:
                        news_pop[int(r[0])] = float(r[1] or 0)
                    except (TypeError, ValueError):
                        news_pop[int(r[0])] = 0.0
        except Exception:
            news_pop = {}
    note_likes: dict[str, int] = {}
    if note_ids and social_db.is_file():
        try:
            with sqlite3.connect(str(social_db)) as conn:
                q = ",".join("?" * len(note_ids))
                for r in conn.execute(
                    f"SELECT note_id, COUNT(*) FROM likes WHERE note_id IN ({q}) GROUP BY note_id",
                    note_ids,
                ):
                    note_likes[str(r[0])] = int(r[1] or 0)
        except Exception:
            note_likes = {}
    for items in lanes.values():
        for it in items:
            nid = it.pop("_news_id", None)
            sid = it.pop("_social_note_id", None)
            if isinstance(nid, int) and nid in news_pop:
                pop = news_pop[nid]
                it["popularity"] = pop
                it["like_count"] = max(0, int(round(pop)))
            elif sid:
                n = note_likes.get(str(sid), 0)
                it["popularity"] = float(n)
                it["like_count"] = n


def _news_blocked(out: list[dict[str, Any]], item: dict[str, Any]) -> bool:
    if len(out) < 2:
        return False
    prev = out[-2:]
    if any(it.get("lane") != "news" for it in prev):
        return False
    source = item.get("source") or ""
    return all((it.get("source") or "") == source and source for it in prev)


def _user_blocked(out: list[dict[str, Any]], item: dict[str, Any]) -> bool:
    if not out:
        return False
    prev = out[-1]
    if prev.get("lane") == "news":
        return False
    uid = item.get("user_id") or ""
    return bool(uid) and uid == (prev.get("user_id") or "")


def _take(rows: list[dict[str, Any]], out: list[dict[str, Any]], lane: str, *, relax: bool) -> dict[str, Any] | None:
    for i, item in enumerate(rows):
        if not relax and lane == "news" and _news_blocked(out, item):
            continue
        if not relax and lane == "user_note" and _user_blocked(out, item):
            continue
        return rows.pop(i)
    return None


def _pick(lanes: dict[str, list[dict[str, Any]]], out: list[dict[str, Any]], slot: str) -> dict[str, Any] | None:
    for lane in FALLBACK[slot]:
        got = _take(lanes[lane], out, lane, relax=False)
        if got:
            return got
    for lane in FALLBACK[slot]:
        got = _take(lanes[lane], out, lane, relax=True)
        if got:
            return got
    return None


def mix_home_feed(
    *,
    limit: int = 20,
    offset: int = 0,
    user_tags: list[str] | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """生成槽位序列再切片。同一请求内不重复 note_id。"""
    limit = max(1, min(int(limit), 60))
    offset = max(0, int(offset))
    tags = [t.strip() for t in (user_tags or []) if t and t.strip()]
    if not tags and user_id:
        tags = get_user_profile_tags(user_id)
    lanes = _load_candidates(tags)
    out: list[dict[str, Any]] = []
    while len(out) < MAX_SEQ:
        item = _pick(lanes, out, SLOT[len(out) % 6])
        if item is None:
            break
        item.pop("_tennis", None)
        out.append(item)
    return out[offset : offset + limit]
