"""用户行为反馈（点击/点赞等）→ 更新 popularity。"""
from __future__ import annotations

import sqlite3

from rec.timeutil import to_iso, utc_now


def record_feedback(user_id: str, article_id: int, action: str) -> None:
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    if not user_id.strip():
        raise ValueError("user_id 不能为空")
    if action not in {"view", "click", "like", "dislike", "bookmark", "read"}:
        raise ValueError("action 非法")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO news_feedback(user_id, article_id, action, created_at) VALUES(?, ?, ?, ?)",
            (user_id.strip(), int(article_id), action, to_iso(utc_now())),
        )
        if action in {"click", "like", "bookmark", "read"}:
            conn.execute(
                "UPDATE news_articles SET popularity = popularity + ? WHERE id = ?",
                (
                    1.0
                    if action == "click"
                    else 3.5
                    if action in {"like", "bookmark"}
                    else 1.8,
                    int(article_id),
                ),
            )
        if action == "dislike":
            conn.execute(
                "UPDATE news_articles SET popularity = popularity - 2.0 WHERE id = ?",
                (int(article_id),),
            )
        conn.commit()
