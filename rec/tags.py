"""标签词表、切分与热门标签建议。"""
from __future__ import annotations

from typing import Any

TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ATP": (" atp ", "atp tour", "atp masters", "atp 250", "atp 500", "atp 1000"),
    "WTA": (" wta ", "wta tour", "wta 250", "wta 500", "wta 1000"),
    "赛事": (
        "tournament",
        "final",
        "semi-final",
        "quarter-final",
        "qualifying",
        "draw",
        "match report",
        "vs ",
        " beat ",
        " defeats ",
        "公开赛",
        "决赛",
        "半决赛",
        "资格赛",
        "对阵",
    ),
    "教学": (
        "coaching",
        "drill",
        "how to",
        "technique",
        "tutorial",
        "lesson",
        "tips",
        "教学",
        "训练",
        "技巧",
    ),
    "阿尔卡拉斯": ("alcaraz", "carlos alcaraz", "阿尔卡拉斯"),
    "德约科维奇": ("djokovic", "novak", "德约科维奇"),
    "辛纳": ("sinner", "jannik", "辛纳"),
    "萨巴伦卡": ("sabalenka", "aryna", "萨巴伦卡"),
    "斯瓦泰克": ("swiatek", "iga", "斯瓦泰克"),
    "平台式发球": ("platform stance", "platform serve", "平台式发球"),
    "单脚式发球": ("pinpoint stance", "pinpoint serve", "单脚式发球"),
    "单手反拍": ("one-handed backhand", "单手反拍"),
    "反东方式单手反拍": ("eastern one-handed backhand", "反东方式单手反拍"),
    "双手反拍": ("two-handed backhand", "双手反拍"),
    "红土": ("clay court", "红土"),
    "草地": ("grass court", "草地"),
    "硬地": ("hard court", "硬地"),
}


def split_tags_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def suggest_tags(limit: int = 40) -> list[str]:
    """从近期文章 tags 统计热门标签，不足时用 TAG_KEYWORDS 补齐。"""
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    with __import__("sqlite3").connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT tags_csv FROM news_articles WHERE tags_csv <> '' "
            "ORDER BY datetime(published_at) DESC LIMIT 500"
        ).fetchall()
    freq: dict[str, int] = {}
    for (csv_tags,) in rows:
        for t in split_tags_csv(csv_tags):
            freq[t] = freq.get(t, 0) + 1
    hot = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    base = [x for x, _ in hot[:limit]]
    if len(base) < 8:
        for t in TAG_KEYWORDS:
            if t not in base:
                base.append(t)
            if len(base) >= limit:
                break
    return base
