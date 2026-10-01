"""用户行为反馈（点击/点赞等）→ 更新 popularity；点赞数按反馈表统计。"""
from __future__ import annotations

import sqlite3
from typing import Any

from rec.timeutil import to_iso, utc_now

# 热度权重（仅影响 popularity 排序，不影响 like_count）
_WEIGHT = {
    "click": 1.0,
    "like": 3.5,
    "bookmark": 3.5,
    "read": 1.8,
    "dislike": -2.0,
}


def count_article_likes(article_id: int, conn: sqlite3.Connection | None = None) -> int:
    """资讯真实点赞人数：同一用户多次 like 只计 1。"""
    aid = int(article_id)

    def _q(c: sqlite3.Connection) -> int:
        row = c.execute(
            """
            SELECT COUNT(DISTINCT user_id) AS c
            FROM news_feedback
            WHERE article_id = ? AND action = 'like'
            """,
            (aid,),
        ).fetchone()
        return int(row[0] if row else 0)

    if conn is not None:
        return _q(conn)
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    with sqlite3.connect(DB_PATH) as c:
        return _q(c)


def count_article_likes_batch(article_ids: list[int]) -> dict[int, int]:
    ids = sorted({int(x) for x in article_ids if x is not None})
    if not ids:
        return {}
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    out = {i: 0 for i in ids}
    with sqlite3.connect(DB_PATH) as conn:
        q = ",".join("?" * len(ids))
        for r in conn.execute(
            f"""
            SELECT article_id, COUNT(DISTINCT user_id) AS c
            FROM news_feedback
            WHERE action = 'like' AND article_id IN ({q})
            GROUP BY article_id
            """,
            ids,
        ):
            out[int(r[0])] = int(r[1] or 0)
    return out


def record_feedback(user_id: str, article_id: int, action: str) -> dict[str, Any]:
    """写入反馈。like / dislike（取消赞）按用户去重；返回 like_count。"""
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id 不能为空")
    if action not in {"view", "click", "like", "dislike", "bookmark", "read"}:
        raise ValueError("action 非法")
    aid = int(article_id)
    now = to_iso(utc_now())
    liked = False
    with sqlite3.connect(DB_PATH) as conn:
        if action == "like":
            exists = conn.execute(
                """
                SELECT 1 FROM news_feedback
                WHERE user_id = ? AND article_id = ? AND action = 'like'
                LIMIT 1
                """,
                (uid, aid),
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO news_feedback(user_id, article_id, action, created_at) VALUES(?, ?, ?, ?)",
                    (uid, aid, "like", now),
                )
                conn.execute(
                    "UPDATE news_articles SET popularity = popularity + ? WHERE id = ?",
                    (_WEIGHT["like"], aid),
                )
            liked = True
        elif action == "dislike":
            # 详情页取消赞走 dislike：删掉该用户的 like，并回退热度
            rows = conn.execute(
                """
                SELECT COUNT(*) AS c FROM news_feedback
                WHERE user_id = ? AND article_id = ? AND action = 'like'
                """,
                (uid, aid),
            ).fetchone()
            n = int(rows[0] if rows else 0)
            if n:
                conn.execute(
                    """
                    DELETE FROM news_feedback
                    WHERE user_id = ? AND article_id = ? AND action = 'like'
                    """,
                    (uid, aid),
                )
                conn.execute(
                    "UPDATE news_articles SET popularity = popularity - ? WHERE id = ?",
                    (_WEIGHT["like"] * n, aid),
                )
            # 仍记一条 dislike 供以后分析（不重复堆热度惩罚多次取消）
            conn.execute(
                "INSERT INTO news_feedback(user_id, article_id, action, created_at) VALUES(?, ?, ?, ?)",
                (uid, aid, "dislike", now),
            )
            liked = False
        else:
            conn.execute(
                "INSERT INTO news_feedback(user_id, article_id, action, created_at) VALUES(?, ?, ?, ?)",
                (uid, aid, action, now),
            )
            w = _WEIGHT.get(action)
            if w:
                conn.execute(
                    "UPDATE news_articles SET popularity = popularity + ? WHERE id = ?",
                    (w, aid),
                )
        conn.commit()
        like_count = count_article_likes(aid, conn)
    return {"ok": True, "liked": liked, "like_count": like_count}
