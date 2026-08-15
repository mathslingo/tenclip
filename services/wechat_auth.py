"""微信小程序登录会话（code2Session + Bearer token）与游客昵称密码登录。"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, Field

from services.social import (
    _conn,
    _nickname_free,
    alloc_user_id,
    find_user_id_by_nickname,
    get_user,
    nickname_available,
    normalize_nickname,
    upsert_user,
)

logger = logging.getLogger(__name__)

SESSION_TTL_SEC = 30 * 24 * 3600  # 30 days
ADMIN_TOKEN_ENV = "TENCLIP_ADMIN_TOKEN"
_PASSWORD_RE = re.compile(r"^\d{6}$")
_NICK_MIN = 2
_NICK_MAX = 20


class WechatLoginBody(BaseModel):
    code: str = Field(..., min_length=1)
    device_hint: str = ""


class GuestRegisterBody(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=40)
    password: str = Field(..., min_length=6, max_length=6)
    device_hint: str = ""


class GuestLoginBody(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=40)
    password: str = Field(..., min_length=6, max_length=6)
    device_hint: str = ""


class ProfileUpdateBody(BaseModel):
    nickname: str = ""
    avatar_url: str = ""
    bio: str = ""
    gender: int = 0
    birthday: str = ""
    phone: str = ""
    email: str = ""
    country: str = ""
    province: str = ""
    city: str = ""
    location: str = ""
    tags: list[str] = Field(default_factory=list)
    tennis_hand: str = ""
    tennis_level: str = ""
    tennis_style: str = ""
    preferred_surface: str = ""


def _wechat_appid() -> str:
    return (os.environ.get("TENCLIP_WECHAT_APPID") or "").strip()


def _wechat_secret() -> str:
    return (os.environ.get("TENCLIP_WECHAT_SECRET") or "").strip()


def _wechat_mock() -> bool:
    return (os.environ.get("TENCLIP_WECHAT_MOCK") or "").strip() in ("1", "true", "True", "yes")


def _new_user_id(conn) -> str:
    return alloc_user_id(conn)


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    ).hex()
    return f"pbkdf2_sha256$120000${salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds_s, salt, digest = (stored or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds
        ).hex()
        return secrets.compare_digest(check, digest)
    except Exception:
        return False


def _validate_nickname(nickname: str) -> str:
    nick = normalize_nickname(nickname)
    if len(nick) < _NICK_MIN or len(nick) > _NICK_MAX:
        raise ValueError(f"昵称长度需 {_NICK_MIN}–{_NICK_MAX} 个字符")
    if nick.lower() in ("admin", "system", "null", "undefined"):
        raise ValueError("昵称不可用")
    return nick


def _validate_password(password: str) -> str:
    pwd = (password or "").strip()
    if not _PASSWORD_RE.match(pwd):
        raise ValueError("密码须为 6 位数字")
    return pwd


def _issue_session(conn, user_id: str, *, device_hint: str = "") -> tuple[str, float]:
    now = time.time()
    token = _new_token()
    expires = now + SESSION_TTL_SEC
    conn.execute(
        """
        INSERT INTO sessions (token, user_id, created_at, expires_at, device_hint)
        VALUES (?, ?, ?, ?, ?)
        """,
        (token, user_id, now, expires, (device_hint or "")[:64]),
    )
    return token, expires


def code2session(code: str) -> dict[str, Any]:
    """调用微信 jscode2session，返回 openid / session_key / unionid。"""
    code = (code or "").strip()
    if not code:
        raise ValueError("code required")

    if _wechat_mock():
        # 本地调试：用 code 派生稳定假 openid
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:28]
        return {
            "openid": "mock_" + digest,
            "session_key": "mock_session",
            "unionid": "",
        }

    appid = _wechat_appid()
    secret = _wechat_secret()
    if not appid or not secret:
        raise RuntimeError("微信登录未配置：请设置 TENCLIP_WECHAT_APPID / TENCLIP_WECHAT_SECRET")

    qs = urlencode(
        {
            "appid": appid,
            "secret": secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    url = "https://api.weixin.qq.com/sns/jscode2session?" + qs
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as e:
        logger.warning("jscode2session network error: %s", e)
        raise RuntimeError("微信登录服务暂时不可用") from e

    try:
        data = json.loads(raw)
    except Exception as e:
        raise RuntimeError("微信登录响应无效") from e

    errcode = data.get("errcode")
    if errcode:
        logger.warning("jscode2session err: %s %s", errcode, data.get("errmsg"))
        raise ValueError(data.get("errmsg") or f"微信登录失败({errcode})")

    openid = (data.get("openid") or "").strip()
    if not openid:
        raise ValueError("微信未返回 openid")
    return {
        "openid": openid,
        "session_key": data.get("session_key") or "",
        "unionid": (data.get("unionid") or "").strip(),
    }


def _user_public(user: dict[str, Any]) -> dict[str, Any]:
    out = dict(user or {})
    # 不对外暴露 openid / 密码哈希
    out.pop("openid", None)
    out.pop("password_hash", None)
    out.pop("_token", None)
    return out


def login_with_wechat_code(code: str, *, device_hint: str = "") -> dict[str, Any]:
    wx = code2session(code)
    openid = wx["openid"]
    unionid = wx.get("unionid") or ""
    now = time.time()
    is_new = False

    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE openid = ?", (openid,)
        ).fetchone()
        if row:
            uid = row["user_id"]
            keys = set(row.keys())
            if int((row["status"] if "status" in keys else 0) or 0) == 1:
                raise ValueError("账号已禁用")
            conn.execute(
                """
                UPDATE users
                SET unionid=CASE WHEN ? <> '' THEN ? ELSE unionid END,
                    last_login_at=?,
                    updated_at=?,
                    login_count=COALESCE(login_count, 0) + 1
                WHERE user_id=?
                """,
                (unionid, unionid, now, now, uid),
            )
        else:
            is_new = True
            uid = _new_user_id(conn)
            # 临时唯一昵称，完善资料时由用户改成正式昵称
            nick = f"球友{uid}"
            conn.execute(
                """
                INSERT INTO users (
                    user_id, nickname, avatar_url, bio, created_at, updated_at,
                    openid, unionid, session_version, profile_completed, last_login_at,
                    login_count, status, create_id, update_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 1, 0, 'wechat', '')
                """,
                (uid, nick, "", "", now, now, openid, unionid, now),
            )

        token, expires = _issue_session(conn, uid, device_hint=device_hint)
        conn.commit()

    user = get_user(uid) or {"user_id": uid}
    return {
        "token": token,
        "expires_at": expires,
        "is_new": is_new,
        "user": _user_public(user),
    }


def register_guest(nickname: str, password: str, *, device_hint: str = "") -> dict[str, Any]:
    nick = _validate_nickname(nickname)
    pwd = _validate_password(password)
    now = time.time()

    with _conn() as conn:
        if not _nickname_free(conn, nick):
            raise ValueError("昵称已被占用")
        uid = _new_user_id(conn)
        ph = _hash_password(pwd)
        try:
            conn.execute(
                """
                INSERT INTO users (
                    user_id, nickname, avatar_url, bio, created_at, updated_at,
                    openid, unionid, session_version, profile_completed, last_login_at,
                    login_count, status, create_id, update_id, password_hash
                ) VALUES (?, ?, '', '', ?, ?, '', '', 0, 1, ?, 1, 0, 'guest', '', ?)
                """,
                (uid, nick, now, now, now, ph),
            )
        except Exception as e:
            # 唯一索引竞态
            if "UNIQUE" in str(e).upper() or "unique" in str(e).lower():
                raise ValueError("昵称已被占用") from e
            raise
        token, expires = _issue_session(conn, uid, device_hint=device_hint)
        conn.commit()

    user = get_user(uid) or {"user_id": uid}
    return {
        "token": token,
        "expires_at": expires,
        "is_new": True,
        "user": _user_public(user),
    }


def login_guest(nickname: str, password: str, *, device_hint: str = "") -> dict[str, Any]:
    nick = _validate_nickname(nickname)
    pwd = _validate_password(password)
    uid = find_user_id_by_nickname(nick)
    if not uid:
        raise ValueError("昵称或密码错误")

    now = time.time()
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if not row:
            raise ValueError("昵称或密码错误")
        keys = set(row.keys())
        if int((row["status"] if "status" in keys else 0) or 0) == 1:
            raise ValueError("账号已禁用")
        create_id = (row["create_id"] if "create_id" in keys else "") or ""
        ph = (row["password_hash"] if "password_hash" in keys else "") or ""
        if create_id != "guest" or not ph:
            raise ValueError("该账号请使用微信登录")
        if not _verify_password(pwd, ph):
            raise ValueError("昵称或密码错误")
        conn.execute(
            """
            UPDATE users
            SET last_login_at=?, updated_at=?, login_count=COALESCE(login_count, 0) + 1
            WHERE user_id=?
            """,
            (now, now, uid),
        )
        token, expires = _issue_session(conn, uid, device_hint=device_hint)
        conn.commit()

    user = get_user(uid) or {"user_id": uid}
    return {
        "token": token,
        "expires_at": expires,
        "is_new": False,
        "user": _user_public(user),
    }


def resolve_token(authorization: str | None) -> dict[str, Any] | None:
    """解析 Bearer token，返回用户公开信息；无效返回 None。"""
    if not authorization:
        return None
    raw = authorization.strip()
    if raw.lower().startswith("bearer "):
        token = raw[7:].strip()
    else:
        token = raw
    if not token:
        return None
    now = time.time()
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT s.token, s.user_id, s.expires_at, u.session_version
            FROM sessions s
            JOIN users u ON u.user_id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if not row:
            return None
        if float(row["expires_at"] or 0) < now:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            conn.commit()
            return None
        user = get_user(row["user_id"])
        if not user:
            return None
        user["_token"] = token
        return user


def require_user(authorization: str | None) -> dict[str, Any]:
    user = resolve_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def logout_token(authorization: str | None) -> bool:
    user = resolve_token(authorization)
    if not user:
        return False
    token = user.get("_token")
    if not token:
        return False
    with _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()
    return True


def update_profile(
    user_id: str,
    *,
    nickname: str = "",
    avatar_url: str = "",
    bio: str = "",
    gender: int = 0,
    birthday: str = "",
    phone: str = "",
    email: str = "",
    country: str = "",
    province: str = "",
    city: str = "",
    location: str = "",
    tags: list[str] | None = None,
    tennis_hand: str = "",
    tennis_level: str = "",
    tennis_style: str = "",
    preferred_surface: str = "",
) -> dict[str, Any]:
    nick_in = normalize_nickname(nickname)
    if nick_in:
        nick_in = _validate_nickname(nick_in)
        if not nickname_available(nick_in, exclude_user_id=user_id):
            raise ValueError("昵称已被占用")

    upsert_user(user_id, nickname=nick_in, avatar_url=avatar_url, bio=bio)

    now = time.time()
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    with _conn() as conn:
        conn.execute(
            """
            UPDATE users SET
                profile_completed=1,
                updated_at=?,
                update_id='self',
                gender=?,
                birthday=?,
                phone=?,
                email=?,
                country=?,
                province=?,
                city=?,
                location=CASE WHEN ? <> '' THEN ? ELSE location END,
                tags_json=?,
                tennis_hand=CASE WHEN ? <> '' THEN ? ELSE tennis_hand END,
                tennis_level=CASE WHEN ? <> '' THEN ? ELSE tennis_level END,
                tennis_style=CASE WHEN ? <> '' THEN ? ELSE tennis_style END,
                preferred_surface=CASE WHEN ? <> '' THEN ? ELSE preferred_surface END
            WHERE user_id=?
            """,
            (
                now,
                int(gender or 0),
                (birthday or "").strip(),
                (phone or "").strip(),
                (email or "").strip(),
                (country or "").strip(),
                (province or "").strip(),
                (city or "").strip(),
                (location or "").strip(),
                (location or "").strip(),
                tags_json,
                (tennis_hand or "").strip(),
                (tennis_hand or "").strip(),
                (tennis_level or "").strip(),
                (tennis_level or "").strip(),
                (tennis_style or "").strip(),
                (tennis_style or "").strip(),
                (preferred_surface or "").strip(),
                (preferred_surface or "").strip(),
                user_id,
            ),
        )
        conn.commit()
    return _user_public(get_user(user_id) or {})


def revoke_user_sessions(user_id: str) -> dict[str, Any]:
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id required")
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET session_version=session_version+1, updated_at=? WHERE user_id=?",
            (time.time(), uid),
        )
        conn.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        conn.commit()
    return {"ok": True, "user_id": uid}


def list_users_admin(*, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT u.user_id, u.nickname, u.avatar_url, u.bio, u.openid,
                   u.profile_completed, u.last_login_at, u.created_at, u.create_id,
                   (SELECT COUNT(*) FROM notes n WHERE n.user_id = u.user_id) AS note_count
            FROM users u
            ORDER BY COALESCE(u.last_login_at, u.created_at) DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    out = []
    for r in rows:
        keys = set(r.keys())
        openid = r["openid"] or ""
        masked = ""
        if openid:
            masked = openid[:4] + "****" + openid[-4:] if len(openid) > 8 else "****"
        create_id = (r["create_id"] if "create_id" in keys else "wechat") or "wechat"
        out.append(
            {
                "user_id": r["user_id"],
                "nickname": r["nickname"],
                "avatar_url": r["avatar_url"],
                "bio": r["bio"],
                "openid_masked": masked,
                "create_id": create_id,
                "account_type": "guest" if create_id == "guest" else "wechat",
                "profile_completed": int(r["profile_completed"] or 0),
                "last_login_at": r["last_login_at"],
                "created_at": r["created_at"],
                "note_count": int(r["note_count"] or 0),
            }
        )
    return out


def _check_admin(authorization: str | None, admin_key: str | None) -> None:
    expected = (os.environ.get(ADMIN_TOKEN_ENV) or "").strip()
    if not expected:
        # 未配置时：仅允许 MOCK 环境或本地，避免裸奔
        if not _wechat_mock():
            raise HTTPException(status_code=503, detail="未配置 TENCLIP_ADMIN_TOKEN")
        return
    provided = (admin_key or "").strip()
    if not provided and authorization:
        raw = authorization.strip()
        if raw.lower().startswith("bearer "):
            provided = raw[7:].strip()
        else:
            provided = raw
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="admin forbidden")


def register_auth_routes(api) -> None:
    @api.post("/api/auth/wechat/login")
    def api_wechat_login(payload: WechatLoginBody):
        try:
            return login_with_wechat_code(payload.code, device_hint=payload.device_hint)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e

    @api.post("/api/auth/guest/register")
    def api_guest_register(payload: GuestRegisterBody):
        try:
            return register_guest(
                payload.nickname, payload.password, device_hint=payload.device_hint
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.post("/api/auth/guest/login")
    def api_guest_login(payload: GuestLoginBody):
        try:
            return login_guest(
                payload.nickname, payload.password, device_hint=payload.device_hint
            )
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e

    @api.get("/api/auth/nickname/check")
    def api_nickname_check(
        nickname: str = Query(..., min_length=1),
        authorization: str | None = Header(default=None),
    ):
        nick = normalize_nickname(nickname)
        exclude = ""
        user = resolve_token(authorization)
        if user:
            exclude = user.get("user_id") or ""
        try:
            if nick:
                _validate_nickname(nick)
            available = nickname_available(nick, exclude_user_id=exclude) if nick else False
        except ValueError as e:
            return {"nickname": nick, "available": False, "reason": str(e)}
        return {
            "nickname": nick,
            "available": available,
            "reason": "" if available else "昵称已被占用",
        }

    @api.get("/api/auth/me")
    def api_auth_me(authorization: str | None = Header(default=None)):
        user = require_user(authorization)
        return _user_public(user)

    @api.post("/api/auth/logout")
    def api_auth_logout(authorization: str | None = Header(default=None)):
        ok = logout_token(authorization)
        return {"ok": ok}

    @api.post("/api/auth/profile")
    def api_auth_profile(
        payload: ProfileUpdateBody,
        authorization: str | None = Header(default=None),
    ):
        user = require_user(authorization)
        try:
            return update_profile(
                user["user_id"],
                nickname=payload.nickname,
                avatar_url=payload.avatar_url,
                bio=payload.bio,
                gender=payload.gender,
                birthday=payload.birthday,
                phone=payload.phone,
                email=payload.email,
                country=payload.country,
                province=payload.province,
                city=payload.city,
                location=payload.location,
                tags=payload.tags,
                tennis_hand=payload.tennis_hand,
                tennis_level=payload.tennis_level,
                tennis_style=payload.tennis_style,
                preferred_surface=payload.preferred_surface,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.get("/api/admin/users")
    def api_admin_users(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        authorization: str | None = Header(default=None),
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    ):
        _check_admin(authorization, x_admin_token)
        return {"items": list_users_admin(limit=limit, offset=offset)}

    @api.post("/api/admin/users/{user_id}/revoke")
    def api_admin_revoke(
        user_id: str,
        authorization: str | None = Header(default=None),
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    ):
        _check_admin(authorization, x_admin_token)
        try:
            return revoke_user_sessions(user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
