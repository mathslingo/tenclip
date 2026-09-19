"""推荐全量笔记目录：用户笔记 + 资讯，统一 10 位 note_id。"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _REPO_ROOT / "data" / "rec_notes.db"
SOCIAL_DB = _REPO_ROOT / "data" / "social.db"
NEWS_DB = _REPO_ROOT / "data" / "news_feed.db"

NOTE_ID_START = 1_000_000_000
NOTE_ID_MAX = 9_999_999_999
KIND_USER = "user_note"
KIND_NEWS = "news"
STATUS_ACTIVE = "active"
STATUS_DELETED = "deleted"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_rec_catalog() -> None:
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rec_note_id_seq (
                name TEXT PRIMARY KEY,
                next_id INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rec_notes (
                note_id TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                user_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                image_url TEXT NOT NULL DEFAULT '',
                images_json TEXT NOT NULL DEFAULT '[]',
                tags_csv TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                extra_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(source_kind, source_ref)
            );
            CREATE INDEX IF NOT EXISTS idx_rec_notes_kind_time
                ON rec_notes(source_kind, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_rec_notes_status_pub
                ON rec_notes(status, published_at DESC);
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO rec_note_id_seq(name, next_id)
            VALUES ('note_id', ?)
            """,
            (NOTE_ID_START,),
        )
        conn.commit()


def _alloc_note_id(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT next_id FROM rec_note_id_seq WHERE name='note_id'"
    ).fetchone()
    n = int(row["next_id"] if row else NOTE_ID_START)
    if n < NOTE_ID_START or n > NOTE_ID_MAX:
        raise RuntimeError(f"note_id 序列非法或耗尽: {n}")
    conn.execute(
        "UPDATE rec_note_id_seq SET next_id=? WHERE name='note_id'",
        (n + 1,),
    )
    return f"{n:010d}"


def _upsert(
    *,
    source_kind: str,
    source_ref: str,
    user_id: str = "",
    title: str = "",
    body: str = "",
    summary: str = "",
    image_url: str = "",
    images: list[str] | None = None,
    tags_csv: str = "",
    url: str = "",
    published_at: str = "",
    created_at: float | None = None,
    extra: dict[str, Any] | None = None,
    status: str = STATUS_ACTIVE,
) -> str:
    init_rec_catalog()
    now = time.time()
    created = float(created_at if created_at is not None else now)
    images_json = json.dumps(images or [], ensure_ascii=False)
    extra_json = json.dumps(extra or {}, ensure_ascii=False)
    with _conn() as conn:
        existing = conn.execute(
            "SELECT note_id FROM rec_notes WHERE source_kind=? AND source_ref=?",
            (source_kind, source_ref),
        ).fetchone()
        if existing:
            note_id = str(existing["note_id"])
            conn.execute(
                """
                UPDATE rec_notes SET
                    status=?, user_id=?, title=?, body=?, summary=?,
                    image_url=?, images_json=?, tags_csv=?, url=?,
                    published_at=?, updated_at=?, extra_json=?
                WHERE note_id=?
                """,
                (
                    status,
                    user_id or "",
                    title or "",
                    body or "",
                    summary or "",
                    image_url or "",
                    images_json,
                    tags_csv or "",
                    url or "",
                    published_at or "",
                    now,
                    extra_json,
                    note_id,
                ),
            )
        else:
            note_id = _alloc_note_id(conn)
            conn.execute(
                """
                INSERT INTO rec_notes (
                    note_id, source_kind, source_ref, status, user_id,
                    title, body, summary, image_url, images_json, tags_csv,
                    url, published_at, created_at, updated_at, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    source_kind,
                    source_ref,
                    status,
                    user_id or "",
                    title or "",
                    body or "",
                    summary or "",
                    image_url or "",
                    images_json,
                    tags_csv or "",
                    url or "",
                    published_at or "",
                    created,
                    now,
                    extra_json,
                ),
            )
        conn.commit()
    return note_id


def user_source_ref(social_note_id: str) -> str:
    nid = (social_note_id or "").strip()
    if nid.startswith("note-"):
        nid = nid[5:]
    return f"user:{nid}"


def news_source_ref(news_id: int | str) -> str:
    return f"news:{int(news_id)}"


def upsert_user_note(note: dict[str, Any]) -> str:
    """把 social.notes 一条同步进目录。note 为 get_note / 行字典。"""
    sid = str(note.get("note_id") or note.get("id") or "").strip()
    if sid.startswith("note-"):
        sid = sid[5:]
    if not sid:
        raise ValueError("user note missing id")
    images = note.get("images") or []
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = []
    if not isinstance(images, list):
        images = []
    images = [str(x).strip() for x in images if str(x).strip()]
    created = note.get("created_at")
    try:
        created_f = float(created) if created is not None else time.time()
    except (TypeError, ValueError):
        created_f = time.time()
    pub = note.get("published_at") or note.get("created_at_iso") or ""
    if not pub and created_f:
        pub = datetime.fromtimestamp(created_f, tz=timezone.utc).isoformat()
    title = (note.get("title") or "").strip()
    body = (note.get("body") or note.get("summary") or "").strip()
    return _upsert(
        source_kind=KIND_USER,
        source_ref=user_source_ref(sid),
        user_id=str(note.get("user_id") or ""),
        title=title,
        body=body,
        summary=body,
        image_url=(images[0] if images else (note.get("image_url") or "")),
        images=images,
        tags_csv=",".join(note.get("tags") or []) if isinstance(note.get("tags"), list) else str(note.get("tags_csv") or ""),
        url=str(note.get("url") or ""),
        published_at=str(pub),
        created_at=created_f,
        extra={
            "location_name": note.get("location_name") or "",
            "author_name": note.get("author_name") or note.get("nickname") or "",
        },
        status=STATUS_ACTIVE,
    )


def mark_user_note_deleted(social_note_id: str) -> None:
    init_rec_catalog()
    ref = user_source_ref(social_note_id)
    now = time.time()
    with _conn() as conn:
        conn.execute(
            "UPDATE rec_notes SET status=?, updated_at=? WHERE source_kind=? AND source_ref=?",
            (STATUS_DELETED, now, KIND_USER, ref),
        )
        conn.commit()


def upsert_news_article(article: dict[str, Any]) -> str:
    nid = article.get("id")
    if nid is None:
        raise ValueError("news article missing id")
    images = []
    img = (article.get("image_url") or "").strip()
    if img:
        images = [img]
    created = time.time()
    pub = str(article.get("published_at") or "")
    try:
        dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        created = dt.timestamp()
    except Exception:
        pass
    return _upsert(
        source_kind=KIND_NEWS,
        source_ref=news_source_ref(nid),
        user_id="",
        title=str(article.get("title") or ""),
        body=str(article.get("summary") or ""),
        summary=str(article.get("summary") or ""),
        image_url=img,
        images=images,
        tags_csv=str(article.get("tags_csv") or ""),
        url=str(article.get("url") or ""),
        published_at=pub,
        created_at=created,
        extra={
            "source": article.get("source") or "",
            "source_domain": article.get("source_domain") or "",
            "source_tier": article.get("source_tier"),
        },
        status=STATUS_ACTIVE,
    )


def sync_user_notes_from_db() -> int:
    init_rec_catalog()
    if not SOCIAL_DB.is_file():
        return 0
    with sqlite3.connect(str(SOCIAL_DB)) as sconn:
        sconn.row_factory = sqlite3.Row
        rows = sconn.execute("SELECT * FROM notes").fetchall()
    n = 0
    for r in rows:
        images: list[str] = []
        try:
            images = json.loads(r["images_json"] or "[]")
        except Exception:
            images = []
        if not isinstance(images, list):
            images = []
        loc = ""
        if "location_name" in r.keys():
            loc = r["location_name"] or ""
        upsert_user_note(
            {
                "id": r["id"],
                "note_id": r["id"],
                "user_id": r["user_id"],
                "title": r["title"],
                "body": r["body"],
                "images": images,
                "created_at": r["created_at"],
                "location_name": loc,
            }
        )
        n += 1
    return n


def sync_news_from_db() -> int:
    init_rec_catalog()
    if not NEWS_DB.is_file():
        return 0
    with sqlite3.connect(str(NEWS_DB)) as nconn:
        nconn.row_factory = sqlite3.Row
        rows = nconn.execute(
            """
            SELECT id, source, source_domain, source_tier, title, summary, url,
                   image_url, tags_csv, published_at
            FROM news_articles
            """
        ).fetchall()
    n = 0
    for r in rows:
        upsert_news_article(dict(r))
        n += 1
    return n


def backfill_rec_catalog() -> dict[str, int]:
    """把现网 social.notes + news_articles 同步进目录（幂等）。"""
    user_n = sync_user_notes_from_db()
    news_n = sync_news_from_db()
    logger.info("rec catalog backfill user_notes=%s news=%s", user_n, news_n)
    return {"user_notes": user_n, "news": news_n}


def rec_catalog_stats() -> dict[str, Any]:
    init_rec_catalog()
    with _conn() as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM rec_notes").fetchone()[0])
        active = int(
            conn.execute(
                "SELECT COUNT(*) FROM rec_notes WHERE status=?",
                (STATUS_ACTIVE,),
            ).fetchone()[0]
        )
        by_kind = {
            str(r["source_kind"]): int(r["c"])
            for r in conn.execute(
                "SELECT source_kind, COUNT(*) AS c FROM rec_notes GROUP BY source_kind"
            )
        }
        seq = conn.execute(
            "SELECT next_id FROM rec_note_id_seq WHERE name='note_id'"
        ).fetchone()
    return {
        "rec_notes_db": str(DB_PATH),
        "rec_notes": total,
        "rec_notes_active": active,
        "rec_notes_by_kind": by_kind,
        "rec_note_id_next": int(seq["next_id"]) if seq else NOTE_ID_START,
    }


def list_rec_notes(*, limit: int = 30, offset: int = 0, kind: str = "") -> dict[str, Any]:
    init_rec_catalog()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    kind_s = (kind or "").strip()
    with _conn() as conn:
        if kind_s in (KIND_USER, KIND_NEWS):
            total = int(
                conn.execute(
                    "SELECT COUNT(*) FROM rec_notes WHERE source_kind=? AND status=?",
                    (kind_s, STATUS_ACTIVE),
                ).fetchone()[0]
            )
            rows = conn.execute(
                """
                SELECT * FROM rec_notes
                WHERE source_kind=? AND status=?
                ORDER BY datetime(published_at) DESC, created_at DESC
                LIMIT ? OFFSET ?
                """,
                (kind_s, STATUS_ACTIVE, limit, offset),
            ).fetchall()
        else:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) FROM rec_notes WHERE status=?",
                    (STATUS_ACTIVE,),
                ).fetchone()[0]
            )
            rows = conn.execute(
                """
                SELECT * FROM rec_notes
                WHERE status=?
                ORDER BY datetime(published_at) DESC, created_at DESC
                LIMIT ? OFFSET ?
                """,
                (STATUS_ACTIVE, limit, offset),
            ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        try:
            item["images"] = json.loads(r["images_json"] or "[]")
        except Exception:
            item["images"] = []
        try:
            item["extra"] = json.loads(r["extra_json"] or "{}")
        except Exception:
            item["extra"] = {}
        items.append(item)
    return {"items": items, "total": total, "limit": limit, "offset": offset}
