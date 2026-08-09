"""用户兴趣标签画像。"""
from __future__ import annotations

import json
import sqlite3

from rec.timeutil import to_iso, utc_now


def set_user_profile(user_id: str, tags: list[str]) -> None:
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id 不能为空")
    clean_tags = sorted({t.strip() for t in tags if t and t.strip()})
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO news_user_profile(user_id, tags_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                tags_json=excluded.tags_json,
                updated_at=excluded.updated_at
            """,
            (uid, json.dumps(clean_tags, ensure_ascii=False), to_iso(utc_now())),
        )
        conn.commit()


def get_user_profile_tags(user_id: str | None) -> list[str]:
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    uid = (user_id or "").strip()
    if not uid:
        return []
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT tags_json FROM news_user_profile WHERE user_id=?", (uid,)
        ).fetchone()
    if not row:
        return []
    try:
        data = json.loads(row[0] or "[]")
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    return []
