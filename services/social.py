"""用户笔记 + 关注关系（SQLite）。供小程序发笔记 / 发现流 / 关注粉丝。"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _REPO_ROOT / "data" / "social.db"
NOTE_UPLOAD_DIR = _REPO_ROOT / "data" / "note_uploads"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_social_db() -> None:
    NOTE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                nickname TEXT NOT NULL DEFAULT '',
                avatar_url TEXT NOT NULL DEFAULT '',
                bio TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                images_json TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS follows (
                follower_id TEXT NOT NULL,
                followee_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (follower_id, followee_id),
                FOREIGN KEY (follower_id) REFERENCES users(user_id),
                FOREIGN KEY (followee_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_follows_followee ON follows(followee_id);
            """
        )
        conn.commit()


def upsert_user(
    user_id: str,
    *,
    nickname: str = "",
    avatar_url: str = "",
    bio: str = "",
) -> dict[str, Any]:
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id required")
    now = time.time()
    nick = (nickname or "").strip() or "网球爱好者"
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
        if row:
            nick = nick if nickname.strip() else (row["nickname"] or nick)
            avatar = avatar_url.strip() if avatar_url else (row["avatar_url"] or "")
            bio_v = bio if bio != "" else (row["bio"] or "")
            conn.execute(
                """
                UPDATE users SET nickname=?, avatar_url=?, bio=?, updated_at=?
                WHERE user_id=?
                """,
                (nick, avatar, bio_v, now, uid),
            )
        else:
            conn.execute(
                """
                INSERT INTO users (user_id, nickname, avatar_url, bio, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (uid, nick, avatar_url.strip(), bio.strip(), now, now),
            )
        conn.commit()
    return get_user(uid) or {}


def get_user(user_id: str) -> dict[str, Any] | None:
    uid = (user_id or "").strip()
    if not uid:
        return None
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
        if not row:
            return None
        stats = _stats(conn, uid)
        return {
            "user_id": row["user_id"],
            "nickname": row["nickname"],
            "avatar_url": row["avatar_url"],
            "bio": row["bio"],
            "following": stats["following"],
            "followers": stats["followers"],
            "note_count": stats["note_count"],
        }


def _stats(conn: sqlite3.Connection, user_id: str) -> dict[str, int]:
    following = conn.execute(
        "SELECT COUNT(*) AS n FROM follows WHERE follower_id = ?", (user_id,)
    ).fetchone()["n"]
    followers = conn.execute(
        "SELECT COUNT(*) AS n FROM follows WHERE followee_id = ?", (user_id,)
    ).fetchone()["n"]
    note_count = conn.execute(
        "SELECT COUNT(*) AS n FROM notes WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    return {
        "following": int(following),
        "followers": int(followers),
        "note_count": int(note_count),
    }


def follow(follower_id: str, followee_id: str) -> dict[str, Any]:
    a = (follower_id or "").strip()
    b = (followee_id or "").strip()
    if not a or not b:
        raise ValueError("follower_id and followee_id required")
    if a == b:
        raise ValueError("不能关注自己")
    upsert_user(a)
    upsert_user(b)
    now = time.time()
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO follows (follower_id, followee_id, created_at)
            VALUES (?, ?, ?)
            """,
            (a, b, now),
        )
        conn.commit()
        following = _is_following(conn, a, b)
    return {"ok": True, "following": following, **(get_user(b) or {})}


def unfollow(follower_id: str, followee_id: str) -> dict[str, Any]:
    a = (follower_id or "").strip()
    b = (followee_id or "").strip()
    if not a or not b:
        raise ValueError("follower_id and followee_id required")
    with _conn() as conn:
        conn.execute(
            "DELETE FROM follows WHERE follower_id = ? AND followee_id = ?",
            (a, b),
        )
        conn.commit()
    return {"ok": True, "following": False, **(get_user(b) or {})}


def _is_following(conn: sqlite3.Connection, follower_id: str, followee_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM follows WHERE follower_id = ? AND followee_id = ?",
        (follower_id, followee_id),
    ).fetchone()
    return bool(row)


def is_following(follower_id: str, followee_id: str) -> bool:
    with _conn() as conn:
        return _is_following(conn, follower_id.strip(), followee_id.strip())


def list_follow_users(user_id: str, *, kind: str) -> list[dict[str, Any]]:
    uid = (user_id or "").strip()
    if kind == "followers":
        sql = """
            SELECT u.user_id, u.nickname, u.avatar_url, u.bio, f.created_at
            FROM follows f JOIN users u ON u.user_id = f.follower_id
            WHERE f.followee_id = ?
            ORDER BY f.created_at DESC
        """
    else:
        sql = """
            SELECT u.user_id, u.nickname, u.avatar_url, u.bio, f.created_at
            FROM follows f JOIN users u ON u.user_id = f.followee_id
            WHERE f.follower_id = ?
            ORDER BY f.created_at DESC
        """
    with _conn() as conn:
        rows = conn.execute(sql, (uid,)).fetchall()
    return [
        {
            "user_id": r["user_id"],
            "nickname": r["nickname"],
            "avatar_url": r["avatar_url"],
            "bio": r["bio"],
        }
        for r in rows
    ]


def _note_public(row: sqlite3.Row, author: dict[str, Any] | None = None) -> dict[str, Any]:
    images = []
    try:
        images = json.loads(row["images_json"] or "[]")
    except Exception:
        images = []
    if not isinstance(images, list):
        images = []
    images = [str(x) for x in images if x]
    title = (row["title"] or "").strip()
    body = (row["body"] or "").strip()
    if not title:
        title = (body[:24] + "…") if len(body) > 24 else (body or "笔记")
    author = author or {}
    return {
        "id": "note-" + row["id"],
        "note_id": row["id"],
        "kind": "note",
        "user_id": row["user_id"],
        "title": title,
        "summary": body,
        "body": body,
        "image_url": images[0] if images else "",
        "images": images,
        "source": author.get("nickname") or "球友",
        "author_name": author.get("nickname") or "球友",
        "author_avatar": author.get("avatar_url") or "",
        "url": "",
        "tags": ["笔记"],
        "published_at": _iso(row["created_at"]),
        "created_at": row["created_at"],
        "popularity": 0,
        "score": 160.0,
        "channel": "推荐",
    }


def _iso(ts: float) -> str:
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return ""


def create_note(
    user_id: str,
    *,
    title: str = "",
    body: str = "",
    image_urls: list[str] | None = None,
) -> dict[str, Any]:
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id required")
    upsert_user(uid)
    images = [str(x).strip() for x in (image_urls or []) if str(x).strip()][:9]
    if not (title or "").strip() and not (body or "").strip() and not images:
        raise ValueError("请填写正文或添加图片")
    note_id = uuid.uuid4().hex[:16]
    now = time.time()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO notes (id, user_id, title, body, images_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (note_id, uid, (title or "").strip(), (body or "").strip(), json.dumps(images, ensure_ascii=False), now),
        )
        conn.commit()
    return get_note(note_id) or {}


def get_note(note_id: str) -> dict[str, Any] | None:
    nid = (note_id or "").strip()
    if nid.startswith("note-"):
        nid = nid[5:]
    if not nid:
        return None
    with _conn() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (nid,)).fetchone()
        if not row:
            return None
        author_row = conn.execute(
            "SELECT nickname, avatar_url FROM users WHERE user_id = ?",
            (row["user_id"],),
        ).fetchone()
        author = dict(author_row) if author_row else {}
        return _note_public(row, author)


def list_notes(*, user_id: str | None = None, limit: int = 40, offset: int = 0) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 80))
    offset = max(0, int(offset))
    with _conn() as conn:
        if user_id:
            rows = conn.execute(
                """
                SELECT n.*, u.nickname, u.avatar_url
                FROM notes n LEFT JOIN users u ON u.user_id = n.user_id
                WHERE n.user_id = ?
                ORDER BY n.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id.strip(), limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT n.*, u.nickname, u.avatar_url
                FROM notes n LEFT JOIN users u ON u.user_id = n.user_id
                ORDER BY n.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
    out = []
    for r in rows:
        author = {"nickname": r["nickname"], "avatar_url": r["avatar_url"]}
        out.append(_note_public(r, author))
    return out


def delete_note(note_id: str, user_id: str) -> bool:
    nid = (note_id or "").strip()
    if nid.startswith("note-"):
        nid = nid[5:]
    uid = (user_id or "").strip()
    if not nid or not uid:
        return False
    with _conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM notes WHERE id = ?", (nid,)
        ).fetchone()
        if not row or row["user_id"] != uid:
            return False
        conn.execute("DELETE FROM notes WHERE id = ?", (nid,))
        conn.commit()
    note_dir = NOTE_UPLOAD_DIR / nid
    if note_dir.exists():
        import shutil

        shutil.rmtree(note_dir, ignore_errors=True)
    return True


def save_upload(note_key: str, index: int, data: bytes, suffix: str) -> str:
    """保存上传图片，返回对外路径 /static/notes/{key}/{index}.ext"""
    ext = suffix.lower().lstrip(".")
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    if ext == "jpeg":
        ext = "jpg"
    key = (note_key or uuid.uuid4().hex[:12]).strip()
    dest_dir = NOTE_UPLOAD_DIR / key
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{int(index)}.{ext}"
    (dest_dir / filename).write_bytes(data)
    return f"/static/notes/{key}/{filename}"


def register_social_routes(api) -> None:
    """挂到 FastAPI：笔记、关注、静态图。"""
    from fastapi import File, Form, HTTPException, Query, UploadFile
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field

    class UserUpsert(BaseModel):
        user_id: str
        nickname: str = ""
        avatar_url: str = ""
        bio: str = ""

    class NoteCreate(BaseModel):
        user_id: str
        title: str = ""
        body: str = ""
        image_urls: list[str] = Field(default_factory=list)

    class FollowBody(BaseModel):
        follower_id: str
        followee_id: str

    @api.post("/api/social/users/upsert")
    def api_upsert_user(body: UserUpsert):
        try:
            return upsert_user(
                body.user_id,
                nickname=body.nickname,
                avatar_url=body.avatar_url,
                bio=body.bio,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.get("/api/social/users/{user_id}")
    def api_get_user(
        user_id: str,
        viewer_id: str = Query(""),
    ):
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        if viewer_id:
            user["is_following"] = is_following(viewer_id, user_id)
        return user

    @api.post("/api/social/follow")
    def api_follow(body: FollowBody):
        try:
            return follow(body.follower_id, body.followee_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.post("/api/social/unfollow")
    def api_unfollow(body: FollowBody):
        try:
            return unfollow(body.follower_id, body.followee_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.get("/api/social/users/{user_id}/following")
    def api_following(user_id: str):
        return {"items": list_follow_users(user_id, kind="following")}

    @api.get("/api/social/users/{user_id}/followers")
    def api_followers(user_id: str):
        return {"items": list_follow_users(user_id, kind="followers")}

    @api.post("/api/social/uploads")
    async def api_upload(
        file: UploadFile = File(...),
        key: str = Form(""),
        index: int = Form(0),
    ):
        raw = await file.read()
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片不能超过 8MB")
        name = file.filename or "img.jpg"
        suffix = Path(name).suffix or ".jpg"
        url = save_upload(key or uuid.uuid4().hex[:12], index, raw, suffix)
        return {"url": url, "ok": True}

    @api.post("/api/social/notes")
    def api_create_note(body: NoteCreate):
        try:
            return create_note(
                body.user_id,
                title=body.title,
                body=body.body,
                image_urls=body.image_urls,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.get("/api/social/notes")
    def api_list_notes(
        user_id: str = Query(""),
        limit: int = Query(40, ge=1, le=80),
        offset: int = Query(0, ge=0),
    ):
        return {
            "items": list_notes(
                user_id=user_id or None, limit=limit, offset=offset
            )
        }

    @api.get("/api/social/notes/{note_id}")
    def api_get_note(note_id: str):
        note = get_note(note_id)
        if not note:
            raise HTTPException(status_code=404, detail="note not found")
        return note

    @api.delete("/api/social/notes/{note_id}")
    def api_delete_note(note_id: str, user_id: str = Query(...)):
        ok = delete_note(note_id, user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="无法删除")
        return {"ok": True}

    NOTE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    api.mount(
        "/static/notes",
        StaticFiles(directory=str(NOTE_UPLOAD_DIR)),
        name="note-uploads",
    )
