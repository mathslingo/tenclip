"""用户笔记 + 关注关系（SQLite）。供小程序发笔记 / 发现流 / 关注粉丝。"""
from __future__ import annotations

import json
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import File, Form, Header, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _REPO_ROOT / "data" / "social.db"
NEWS_DB_PATH = _REPO_ROOT / "data" / "news_feed.db"
NOTE_UPLOAD_DIR = _REPO_ROOT / "data" / "note_uploads"


class UserUpsert(BaseModel):
    user_id: str = Field(..., min_length=1)
    nickname: str = ""
    avatar_url: str = ""
    bio: str = ""


class NoteCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    title: str = ""
    body: str = ""
    image_urls: list[str] = Field(default_factory=list)
    location_name: str = ""
    location_address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    event_at: float | None = None  # unix 秒；可选附带时间


class FollowBody(BaseModel):
    follower_id: str = Field(..., min_length=1)
    followee_id: str = Field(..., min_length=1)


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=140)


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _table_has_fk_to(conn: sqlite3.Connection, table: str, ref_table: str, column: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    except sqlite3.Error:
        return False
    for row in rows:
        # row: id, seq, table, from, to, on_update, on_delete, match
        if str(row[2]) == ref_table and str(row[3]) == column:
            return True
    return False


def _rebuild_table_without_note_fk(conn: sqlite3.Connection, table: str, create_sql: str) -> None:
    """SQLite 不能 ALTER 去掉外键；评论/点赞需同时支持用户笔记和新闻 id。"""
    if not _table_has_fk_to(conn, table, "notes", "note_id"):
        return
    tmp = table + "_new"
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute(f"DROP TABLE IF EXISTS {tmp}")
        conn.execute(create_sql.replace(f"CREATE TABLE {table}", f"CREATE TABLE {tmp}", 1))
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        col_csv = ", ".join(cols)
        conn.execute(f"INSERT INTO {tmp} ({col_csv}) SELECT {col_csv} FROM {table}")
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


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
            """
        )
        _ensure_column(conn, "notes", "location_name", "location_name TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "notes", "location_address", "location_address TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "notes", "latitude", "latitude REAL")
        _ensure_column(conn, "notes", "longitude", "longitude REAL")
        _ensure_column(conn, "notes", "event_at", "event_at REAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS follows (
                follower_id TEXT NOT NULL,
                followee_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (follower_id, followee_id),
                FOREIGN KEY (follower_id) REFERENCES users(user_id),
                FOREIGN KEY (followee_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_follows_followee ON follows(followee_id);
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                device_hint TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                note_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_comments_note ON comments(note_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(user_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS likes (
                user_id TEXT NOT NULL,
                note_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (user_id, note_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_likes_note ON likes(note_id);
            CREATE TABLE IF NOT EXISTS bookmarks (
                user_id TEXT NOT NULL,
                note_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (user_id, note_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON bookmarks(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_bookmarks_note ON bookmarks(note_id);
            """
        )
        _rebuild_table_without_note_fk(
            conn,
            "comments",
            """
            CREATE TABLE comments (
                id TEXT PRIMARY KEY,
                note_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """,
        )
        _rebuild_table_without_note_fk(
            conn,
            "likes",
            """
            CREATE TABLE likes (
                user_id TEXT NOT NULL,
                note_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (user_id, note_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """,
        )
        _rebuild_table_without_note_fk(
            conn,
            "bookmarks",
            """
            CREATE TABLE bookmarks (
                user_id TEXT NOT NULL,
                note_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (user_id, note_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """,
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_note ON comments(note_id, created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(user_id, created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_likes_note ON likes(note_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON bookmarks(user_id, created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_note ON bookmarks(note_id)")
        # 登录与会话
        _ensure_column(conn, "users", "openid", "openid TEXT")
        _ensure_column(conn, "users", "unionid", "unionid TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "session_version", "session_version INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "users", "profile_completed", "profile_completed INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "users", "last_login_at", "last_login_at REAL")
        _ensure_column(conn, "users", "login_count", "login_count INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "users", "last_login_ip", "last_login_ip TEXT NOT NULL DEFAULT ''")
        # 资料
        _ensure_column(conn, "users", "gender", "gender INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "users", "birthday", "birthday TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "phone", "phone TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "email", "email TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "country", "country TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "province", "province TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "city", "city TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "location", "location TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "tags_json", "tags_json TEXT NOT NULL DEFAULT '[]'")
        # 账号状态：0 正常 1 禁用 2 注销
        _ensure_column(conn, "users", "status", "status INTEGER NOT NULL DEFAULT 0")
        # create_id：创建来源 / 注册渠道（wechat / guest_upgrade / system）
        _ensure_column(conn, "users", "create_id", "create_id TEXT NOT NULL DEFAULT 'wechat'")
        _ensure_column(conn, "users", "update_id", "update_id TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "password_hash", "password_hash TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "tennis_hand", "tennis_hand TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "tennis_level", "tennis_level TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "tennis_style", "tennis_style TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "preferred_surface", "preferred_surface TEXT NOT NULL DEFAULT ''")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_openid ON users(openid) "
            "WHERE openid IS NOT NULL AND openid <> ''"
        )
        # 先消重再建唯一索引（历史默认昵称「网球爱好者」可能重复）
        _dedupe_nicknames(conn)
        conn.execute("DROP INDEX IF EXISTS idx_users_nickname_ci")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_nickname_ci "
            "ON users(nickname COLLATE NOCASE) "
            "WHERE nickname IS NOT NULL AND TRIM(nickname) <> ''"
        )
        conn.commit()


def _dedupe_nicknames(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT user_id, nickname FROM users
        WHERE nickname IS NOT NULL AND TRIM(nickname) <> ''
        ORDER BY created_at ASC, user_id ASC
        """
    ).fetchall()
    seen: dict[str, str] = {}
    for r in rows:
        nick = (r["nickname"] or "").strip()
        key = nick.casefold()
        uid = r["user_id"]
        if key not in seen:
            seen[key] = uid
            continue
        # 重复：改为「原昵称_后四位uid」
        suffix = str(uid)[-4:]
        new_nick = f"{nick}_{suffix}"
        n = 0
        while new_nick.casefold() in seen:
            n += 1
            new_nick = f"{nick}_{suffix}{n}"
        conn.execute(
            "UPDATE users SET nickname=?, updated_at=? WHERE user_id=?",
            (new_nick, time.time(), uid),
        )
        seen[new_nick.casefold()] = uid


def normalize_nickname(nickname: str) -> str:
    return (nickname or "").strip()


def nickname_available(nickname: str, *, exclude_user_id: str = "") -> bool:
    nick = normalize_nickname(nickname)
    if not nick:
        return False
    with _conn() as conn:
        return _nickname_free(conn, nick, exclude_user_id=(exclude_user_id or "").strip())


def _nickname_free(conn: sqlite3.Connection, nickname: str, *, exclude_user_id: str = "") -> bool:
    nick = normalize_nickname(nickname)
    if not nick:
        return False
    excl = (exclude_user_id or "").strip()
    if excl:
        row = conn.execute(
            """
            SELECT 1 FROM users
            WHERE LOWER(TRIM(nickname)) = LOWER(?) AND user_id <> ?
            LIMIT 1
            """,
            (nick, excl),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT 1 FROM users
            WHERE LOWER(TRIM(nickname)) = LOWER(?)
            LIMIT 1
            """,
            (nick,),
        ).fetchone()
    return row is None


def find_user_id_by_nickname(nickname: str) -> str | None:
    nick = normalize_nickname(nickname)
    if not nick:
        return None
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT user_id FROM users
            WHERE LOWER(TRIM(nickname)) = LOWER(?)
            LIMIT 1
            """,
            (nick,),
        ).fetchone()
        return row["user_id"] if row else None


def alloc_user_id(conn: sqlite3.Connection | None = None) -> str:
    """分配全局 8 位数字 user_id（10000000–99999999），保证唯一。"""
    own = conn is None
    if own:
        conn = _conn()
    try:
        for _ in range(64):
            uid = f"{secrets.randbelow(90000000) + 10000000}"
            hit = conn.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone()
            if not hit:
                return uid
        # 极端碰撞：时间片兜底
        return f"{int(time.time()) % 100000000:08d}"
    finally:
        if own:
            conn.close()


def _sanitize_avatar_url(url: str) -> str:
    """只接受可公网访问的头像；微信本地临时路径一律丢弃。"""
    u = (url or "").strip()
    if not u:
        return ""
    low = u.lower()
    if low.startswith("wxfile://") or low.startswith("file://"):
        return ""
    if "://tmp/" in low or low.startswith("http://tmp"):
        return ""
    if u.startswith("/") or low.startswith("https://") or low.startswith("http://"):
        return u
    return ""


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
    nick_in = normalize_nickname(nickname)
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
        if row:
            nick = nick_in if nick_in else (row["nickname"] or f"球友{uid}")
            if nick_in and not _nickname_free(conn, nick, exclude_user_id=uid):
                raise ValueError("昵称已被占用")
            raw_avatar = (avatar_url or "").strip()
            if not raw_avatar:
                avatar = _sanitize_avatar_url(row["avatar_url"] or "")
            else:
                cleaned = _sanitize_avatar_url(raw_avatar)
                avatar = cleaned if cleaned else _sanitize_avatar_url(row["avatar_url"] or "")
            bio_v = bio if bio != "" else (row["bio"] or "")
            conn.execute(
                """
                UPDATE users SET nickname=?, avatar_url=?, bio=?, updated_at=?
                WHERE user_id=?
                """,
                (nick, avatar, bio_v, now, uid),
            )
        else:
            nick = nick_in or f"球友{uid}"
            if nick_in and not _nickname_free(conn, nick):
                raise ValueError("昵称已被占用")
            conn.execute(
                """
                INSERT INTO users (user_id, nickname, avatar_url, bio, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (uid, nick, _sanitize_avatar_url(avatar_url), bio.strip(), now, now),
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
        keys = set(row.keys())

        def g(name: str, default: Any = ""):
            return row[name] if name in keys else default

        tags = []
        try:
            tags = json.loads(g("tags_json", "[]") or "[]")
        except Exception:
            tags = []
        if not isinstance(tags, list):
            tags = []

        return {
            "user_id": row["user_id"],
            "nickname": row["nickname"],
            "avatar_url": _sanitize_avatar_url(row["avatar_url"] or ""),
            "bio": row["bio"],
            "gender": int(g("gender", 0) or 0),
            "birthday": g("birthday", "") or "",
            "phone": g("phone", "") or "",
            "email": g("email", "") or "",
            "country": g("country", "") or "",
            "province": g("province", "") or "",
            "city": g("city", "") or "",
            "location": g("location", "") or "",
            "tags": tags,
            "status": int(g("status", 0) or 0),
            "create_id": g("create_id", "wechat") or "wechat",
            "update_id": g("update_id", "") or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "following": stats["following"],
            "followers": stats["followers"],
            "note_count": stats["note_count"],
            "profile_completed": int(g("profile_completed", 0) or 0),
            "openid": g("openid", "") or "",
            "last_login_at": g("last_login_at", None),
            "login_count": int(g("login_count", 0) or 0),
            "account_type": "guest" if (g("create_id", "") or "") == "guest" else "wechat",
            "has_password": bool(g("password_hash", "") or ""),
            "tennis_hand": g("tennis_hand", "") or "",
            "tennis_level": g("tennis_level", "") or "",
            "tennis_style": g("tennis_style", "") or "",
            "preferred_surface": g("preferred_surface", "") or "",
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
    return {"ok": True, "following": True, **(get_user(b) or {})}


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


def _row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    try:
        keys = row.keys()
        if key not in keys:
            return default
        v = row[key]
        return default if v is None else v
    except Exception:
        return default


def _note_public(row: sqlite3.Row, author: dict[str, Any] | None = None, viewer_id: str | None = None) -> dict[str, Any]:
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
    lat = _row_get(row, "latitude", None)
    lng = _row_get(row, "longitude", None)
    event_at = _row_get(row, "event_at", None)
    try:
        lat_f = float(lat) if lat is not None else None
    except (TypeError, ValueError):
        lat_f = None
    try:
        lng_f = float(lng) if lng is not None else None
    except (TypeError, ValueError):
        lng_f = None
    try:
        event_f = float(event_at) if event_at is not None else None
    except (TypeError, ValueError):
        event_f = None
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
        "location_name": str(_row_get(row, "location_name", "") or ""),
        "location_address": str(_row_get(row, "location_address", "") or ""),
        "latitude": lat_f,
        "longitude": lng_f,
        "event_at": event_f,
        "event_at_iso": _iso(event_f) if event_f else "",
        "popularity": 0,
        "score": 160.0,
        "channel": "推荐",
        "liked": False,
        "bookmarked": False,
    }
    if viewer_id:
        with _conn() as conn:
            like_row = conn.execute(
                "SELECT 1 FROM likes WHERE user_id = ? AND note_id = ? LIMIT 1",
                (viewer_id, row["id"])
            ).fetchone()
            result["liked"] = bool(like_row)
            
            bookmark_row = conn.execute(
                "SELECT 1 FROM bookmarks WHERE user_id = ? AND note_id = ? LIMIT 1",
                (viewer_id, row["id"])
            ).fetchone()
            result["bookmarked"] = bool(bookmark_row)
    return result


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
    location_name: str = "",
    location_address: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    event_at: float | None = None,
) -> dict[str, Any]:
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id required")
    upsert_user(uid)
    images = [str(x).strip() for x in (image_urls or []) if str(x).strip()][:9]
    if not (title or "").strip() and not (body or "").strip() and not images:
        raise ValueError("请填写正文或添加图片")
    loc_name = (location_name or "").strip()[:80]
    loc_addr = (location_address or "").strip()[:200]
    lat_v: float | None = None
    lng_v: float | None = None
    if latitude is not None and longitude is not None:
        try:
            lat_v = float(latitude)
            lng_v = float(longitude)
            if not (-90 <= lat_v <= 90 and -180 <= lng_v <= 180):
                lat_v, lng_v = None, None
                loc_name, loc_addr = "", ""
        except (TypeError, ValueError):
            lat_v, lng_v = None, None
            loc_name, loc_addr = "", ""
    elif loc_name or loc_addr:
        # 有文案无坐标仍允许保存地址
        pass
    else:
        loc_name, loc_addr = "", ""

    event_v: float | None = None
    if event_at is not None:
        try:
            event_v = float(event_at)
            # 合理范围：2000-01-01 ~ 2100-01-01
            if event_v < 946684800 or event_v > 4102444800:
                event_v = None
        except (TypeError, ValueError):
            event_v = None

    note_id = uuid.uuid4().hex[:16]
    now = time.time()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO notes (
                id, user_id, title, body, images_json, created_at,
                location_name, location_address, latitude, longitude, event_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                uid,
                (title or "").strip(),
                (body or "").strip(),
                json.dumps(images, ensure_ascii=False),
                now,
                loc_name,
                loc_addr,
                lat_v,
                lng_v,
                event_v,
            ),
        )
        conn.commit()
    return get_note(note_id) or {}


def get_note(note_id: str, viewer_id: str | None = None) -> dict[str, Any] | None:
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
        return _note_public(row, author, viewer_id)


def search_notes(q: str, limit: int = 40, offset: int = 0, viewer_id: str | None = None) -> list[dict[str, Any]]:
    keyword = (q or "").strip()
    if not keyword:
        return []
    limit = max(1, min(int(limit), 80))
    offset = max(0, int(offset))
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT n.*, u.nickname, u.avatar_url
            FROM notes n LEFT JOIN users u ON u.user_id = n.user_id
            WHERE n.title LIKE ? OR n.body LIKE ?
            ORDER BY n.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (f"%{keyword}%", f"%{keyword}%", limit, offset),
        ).fetchall()
    return [
        _note_public(
            r, {"nickname": r["nickname"], "avatar_url": r["avatar_url"]}, viewer_id
        )
        for r in rows
    ]


def _news_conn() -> sqlite3.Connection | None:
    if not NEWS_DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(NEWS_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _news_to_item(row: sqlite3.Row) -> dict[str, Any]:
    tags = [t.strip() for t in (row["tags_csv"] or "").split(",") if t.strip()]
    return {
        "id": str(row["id"]),
        "kind": "news",
        "title": row["title"] or "",
        "summary": row["summary"] or "",
        "body": row["summary"] or "",
        "url": (row["url"] or "").strip(),
        "image_url": (row["image_url"] or "").strip(),
        "images": [row["image_url"]] if row["image_url"] else [],
        "tags": tags,
        "tags_csv": row["tags_csv"] or "",
        "source": row["source"] or "资讯",
        "author_name": row["source"] or "资讯",
        "author_avatar": "",
        "published_at": row["published_at"] or "",
        "popularity": float(row["popularity"] or 0),
        "score": 160.0,
        "channel": "推荐",
    }


def search_news_articles(q: str, limit: int = 40, offset: int = 0) -> list[dict[str, Any]]:
    keyword = (q or "").strip()
    if not keyword:
        return []
    limit = max(1, min(int(limit), 80))
    offset = max(0, int(offset))
    conn = _news_conn()
    if not conn:
        return []
    try:
        with conn:
            rows = conn.execute(
                """
                SELECT id, source, source_domain, source_tier, title, summary, url,
                       image_url, tags_csv, published_at, popularity
                FROM news_articles
                WHERE title LIKE ? OR summary LIKE ?
                ORDER BY datetime(published_at) DESC
                LIMIT ? OFFSET ?
                """,
                (f"%{keyword}%", f"%{keyword}%", limit, offset),
            ).fetchall()
    except Exception:
        return []
    return [_news_to_item(r) for r in rows]


def _search_time_key(item: dict[str, Any]) -> float:
    raw = item.get("published_at") or item.get("created_at") or 0
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return datetime.fromisoformat(str(raw)).timestamp()
    except Exception:
        return 0.0


def search_universal(q: str, limit: int = 40, offset: int = 0, viewer_id: str | None = None) -> list[dict[str, Any]]:
    """同时搜索用户笔记和新闻资讯，按时间倒序合并。"""
    keyword = (q or "").strip()
    if not keyword:
        return []
    limit = max(1, min(int(limit), 80))
    offset = max(0, int(offset))
    # 各自多取一些，避免合并后再分页导致某一类过少
    fetch_limit = max(limit, 40)
    notes = search_notes(q, limit=fetch_limit, offset=offset, viewer_id=viewer_id)
    news = search_news_articles(q, limit=fetch_limit, offset=offset)
    merged = sorted(notes + news, key=_search_time_key, reverse=True)
    return merged[:limit]


def list_notes(*, user_id: str | None = None, limit: int = 40, offset: int = 0, viewer_id: str | None = None) -> list[dict[str, Any]]:
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
        out.append(_note_public(r, author, viewer_id))
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
    """挂到 FastAPI：笔记、关注、静态图。写操作需 Bearer。"""

    def _auth_user(authorization: str | None):
        from services.wechat_auth import require_user

        return require_user(authorization)

    @api.post("/api/social/users/upsert")
    def api_upsert_user(
        payload: UserUpsert,
        authorization: str | None = Header(default=None),
    ):
        user = _auth_user(authorization)
        try:
            return upsert_user(
                user["user_id"],
                nickname=payload.nickname,
                avatar_url=payload.avatar_url,
                bio=payload.bio,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.get("/api/social/users/{user_id}")
    def api_get_user(
        user_id: str,
        viewer_id: str = Query(""),
        authorization: str | None = Header(default=None),
    ):
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        viewer = viewer_id
        if not viewer and authorization:
            try:
                from services.wechat_auth import resolve_token

                me = resolve_token(authorization)
                if me:
                    viewer = me["user_id"]
            except Exception:
                viewer = ""
        if viewer:
            user["is_following"] = is_following(viewer, user_id)
        user.pop("openid", None)
        # 对外资料页不暴露联系方式
        if not viewer or viewer != user_id:
            user.pop("phone", None)
            user.pop("email", None)
            user.pop("last_login_at", None)
            user.pop("login_count", None)
            user.pop("has_password", None)
        return user

    @api.post("/api/social/follow")
    def api_follow(
        payload: FollowBody,
        authorization: str | None = Header(default=None),
    ):
        me = _auth_user(authorization)
        try:
            return follow(me["user_id"], payload.followee_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.post("/api/social/unfollow")
    def api_unfollow(
        payload: FollowBody,
        authorization: str | None = Header(default=None),
    ):
        me = _auth_user(authorization)
        try:
            return unfollow(me["user_id"], payload.followee_id)
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
        authorization: str | None = Header(default=None),
    ):
        _auth_user(authorization)
        raw = await file.read()
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片不能超过 8MB")
        name = file.filename or "img.jpg"
        suffix = Path(name).suffix or ".jpg"
        url = save_upload(key or uuid.uuid4().hex[:12], index, raw, suffix)
        return {"url": url, "ok": True}

    @api.post("/api/social/notes")
    def api_create_note(
        payload: NoteCreate,
        authorization: str | None = Header(default=None),
    ):
        me = _auth_user(authorization)
        try:
            return create_note(
                me["user_id"],
                title=payload.title,
                body=payload.body,
                image_urls=payload.image_urls,
                location_name=payload.location_name,
                location_address=payload.location_address,
                latitude=payload.latitude,
                longitude=payload.longitude,
                event_at=payload.event_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.get("/api/social/notes/search")
    def api_search_notes(
        q: str = Query(..., min_length=1),
        limit: int = Query(40, ge=1, le=80),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ):
        viewer_id = None
        try:
            user = _auth_user(authorization)
            viewer_id = user.get("user_id")
        except Exception:
            pass
        return {"items": search_notes(q, limit=limit, offset=offset, viewer_id=viewer_id)}

    @api.get("/api/feed/search")
    def api_search_feed(
        q: str = Query(..., min_length=1),
        limit: int = Query(40, ge=1, le=80),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ):
        viewer_id = None
        try:
            user = _auth_user(authorization)
            viewer_id = user.get("user_id")
        except Exception:
            pass
        return {"items": search_universal(q, limit=limit, offset=offset, viewer_id=viewer_id)}

    @api.get("/api/social/notes")
    def api_list_notes(
        user_id: str = Query(""),
        limit: int = Query(40, ge=1, le=80),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ):
        viewer_id = None
        try:
            user = _auth_user(authorization)
            viewer_id = user.get("user_id")
        except Exception:
            pass
        return {
            "items": list_notes(
                user_id=user_id or None, limit=limit, offset=offset, viewer_id=viewer_id
            )
        }

    @api.get("/api/social/notes/{note_id}")
    def api_get_note(
        note_id: str,
        authorization: str | None = Header(default=None),
    ):
        viewer_id = None
        try:
            user = _auth_user(authorization)
            viewer_id = user.get("user_id")
        except Exception:
            pass
        note = get_note(note_id, viewer_id)
        if not note:
            raise HTTPException(status_code=404, detail="note not found")
        return note

    @api.delete("/api/social/notes/{note_id}")
    def api_delete_note(
        note_id: str,
        user_id: str = Query(""),
        authorization: str | None = Header(default=None),
    ):
        me = _auth_user(authorization)
        ok = delete_note(note_id, me["user_id"])
        if not ok:
            raise HTTPException(status_code=404, detail="无法删除")
        return {"ok": True}

    @api.post("/api/social/notes/{note_id}/comments")
    def api_create_comment(
        note_id: str,
        payload: CommentCreate,
        authorization: str | None = Header(default=None),
    ):
        me = _auth_user(authorization)
        try:
            return create_comment(note_id, me["user_id"], payload.body)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except sqlite3.Error as e:
            raise HTTPException(status_code=400, detail="评论保存失败") from e

    @api.get("/api/social/notes/{note_id}/comments")
    def api_list_comments(
        note_id: str,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
    ):
        viewer = ""
        if authorization:
            try:
                from services.wechat_auth import resolve_token
                me = resolve_token(authorization)
                if me:
                    viewer = me["user_id"]
            except Exception:
                viewer = ""
        return {
            "items": list_comments(note_id, viewer_id=viewer, limit=limit, offset=offset)
        }

    @api.delete("/api/social/notes/{note_id}/comments/{comment_id}")
    def api_delete_comment(
        note_id: str,
        comment_id: str,
        authorization: str | None = Header(default=None),
    ):
        me = _auth_user(authorization)
        ok = delete_comment(comment_id, me["user_id"])
        if not ok:
            raise HTTPException(status_code=404, detail="无法删除")
        return {"ok": True}

    @api.post("/api/social/notes/{note_id}/like")
    def api_like_note(
        note_id: str,
        authorization: str | None = Header(default=None),
    ):
        me = _auth_user(authorization)
        res = toggle_like(note_id, me["user_id"])
        return {"liked": res}

    @api.post("/api/social/notes/{note_id}/bookmark")
    def api_bookmark_note(
        note_id: str,
        authorization: str | None = Header(default=None),
    ):
        me = _auth_user(authorization)
        res = toggle_bookmark(note_id, me["user_id"])
        return {"bookmarked": res}

    NOTE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    api.mount(
        "/static/notes",
        StaticFiles(directory=str(NOTE_UPLOAD_DIR)),
        name="note-uploads",
    )



def toggle_like(note_id: str, user_id: str) -> bool:
    """Toggle like status for a note. Returns True if now liked, False if unliked."""
    nid = (note_id or "").strip()
    if nid.startswith("note-"):
        nid = nid[5:]
    uid = (user_id or "").strip()
    if not nid or not uid:
        return False
    
    with _conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM likes WHERE user_id = ? AND note_id = ? LIMIT 1",
            (uid, nid)
        ).fetchone()
        
        if existing:
            conn.execute("DELETE FROM likes WHERE user_id = ? AND note_id = ?", (uid, nid))
            conn.commit()
            return False
        else:
            ts = time.time()
            try:
                conn.execute(
                    "INSERT INTO likes (user_id, note_id, created_at) VALUES (?, ?, ?)",
                    (uid, nid, ts)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass
            return True


def toggle_bookmark(note_id: str, user_id: str) -> bool:
    """Toggle bookmark status for a note. Returns True if now bookmarked, False if removed."""
    nid = (note_id or "").strip()
    if nid.startswith("note-"):
        nid = nid[5:]
    uid = (user_id or "").strip()
    if not nid or not uid:
        return False
    
    with _conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM bookmarks WHERE user_id = ? AND note_id = ? LIMIT 1",
            (uid, nid)
        ).fetchone()
        
        if existing:
            conn.execute("DELETE FROM bookmarks WHERE user_id = ? AND note_id = ?", (uid, nid))
            conn.commit()
            return False
        else:
            ts = time.time()
            try:
                conn.execute(
                    "INSERT INTO bookmarks (user_id, note_id, created_at) VALUES (?, ?, ?)",
                    (uid, nid, ts)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass
            return True


def create_comment(note_id: str, user_id: str, body: str) -> dict[str, Any]:
    """创建评论。支持用户笔记和新闻文章。"""
    nid = (note_id or "").strip()
    if nid.startswith("note-"):
        nid = nid[5:]
    uid = (user_id or "").strip()
    text = (body or "").strip()
    
    if not nid or not uid or not text:
        raise ValueError("note_id, user_id, body required")
    if len(text) > 140:
        raise ValueError("评论最多140字")
    
    # 检查笔记或文章存在
    note_exists = False
    with _conn() as conn:
        note = conn.execute("SELECT id FROM notes WHERE id = ?", (nid,)).fetchone()
        if note:
            note_exists = True
    
    if not note_exists:
        # 尝试从新闻数据库查询
        news_conn = _news_conn()
        if not news_conn:
            raise ValueError("笔记不存在")
        try:
            news_row = news_conn.execute("SELECT id FROM news_articles WHERE id = ?", (nid,)).fetchone()
            if not news_row:
                raise ValueError("笔记或文章不存在")
        finally:
            news_conn.close()
    
    # 创建评论
    cid = uuid.uuid4().hex[:16]
    now = time.time()
    try:
        with _conn() as conn:
            upsert_user(uid)
            conn.execute(
                """
                INSERT INTO comments (id, note_id, user_id, body, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cid, nid, uid, text, now, now),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValueError("评论保存失败") from e
    return get_comment(cid, uid) or {}


def get_comment(comment_id: str, viewer_id: str = "") -> dict[str, Any] | None:
    """获取单条评论。"""
    cid = (comment_id or "").strip()
    if not cid:
        return None
    
    with _conn() as conn:
        row = conn.execute("SELECT * FROM comments WHERE id = ?", (cid,)).fetchone()
        if not row:
            return None
        
        author = conn.execute(
            "SELECT nickname, avatar_url FROM users WHERE user_id = ?",
            (row["user_id"],),
        ).fetchone()
        author_data = dict(author) if author else {}
        
        return {
            "id": row["id"],
            "note_id": row["note_id"],
            "user_id": row["user_id"],
            "body": row["body"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "author_name": author_data.get("nickname", "球友"),
            "author_avatar": author_data.get("avatar_url", ""),
            "can_delete": viewer_id and (viewer_id == row["user_id"]),
        }


def list_comments(note_id: str, viewer_id: str = "", limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """获取笔记的评论列表。"""
    nid = (note_id or "").strip()
    if nid.startswith("note-"):
        nid = nid[5:]
    if not nid:
        return []
    
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT c.*, u.nickname, u.avatar_url
            FROM comments c
            LEFT JOIN users u ON u.user_id = c.user_id
            WHERE c.note_id = ?
            ORDER BY c.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (nid, limit, offset),
        ).fetchall()
    
    return [
        {
            "id": r["id"],
            "note_id": r["note_id"],
            "user_id": r["user_id"],
            "body": r["body"],
            "created_at": r["created_at"],
            "author_name": r["nickname"] or "球友",
            "author_avatar": r["avatar_url"] or "",
            "can_delete": viewer_id and (viewer_id == r["user_id"]),
        }
        for r in rows
    ]


def delete_comment(comment_id: str, user_id: str) -> bool:
    """删除评论（仅评论者）。"""
    cid = (comment_id or "").strip()
    uid = (user_id or "").strip()
    
    if not cid or not uid:
        return False
    
    with _conn() as conn:
        row = conn.execute("SELECT user_id FROM comments WHERE id = ?", (cid,)).fetchone()
        if not row or row["user_id"] != uid:
            return False
        
        conn.execute("DELETE FROM comments WHERE id = ?", (cid,))
        conn.commit()
    
    return True
