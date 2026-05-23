"""小红书 Cookie：文件 / 环境变量，与旧版 xhs_preview 使用相同约定。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_COOKIE_FILE = _REPO_ROOT / "data" / "xhs_cookie.txt"

_file_cache: dict[str, Any] = {}


def repo_root() -> Path:
    return _REPO_ROOT


def default_cookie_path() -> Path:
    custom = os.environ.get("TENCLIP_XHS_COOKIE_FILE", "").strip()
    return Path(custom) if custom else _DEFAULT_COOKIE_FILE


def _parse_semicolon(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                out[k] = v
    return out


def _parse_netscape(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7 and parts[5]:
            out[parts[5]] = parts[6]
    return out


def parse_cookie_blob(raw: str) -> dict[str, str]:
    raw = raw.strip()
    if not raw:
        return {}
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    for line in raw.splitlines():
        ls = line.strip()
        if ls and not ls.startswith("#") and ls.count("\t") >= 6:
            return _parse_netscape(raw)
        break
    return _parse_semicolon(raw)


def load_cookies_from_file(path: Path | None = None) -> dict[str, str]:
    path = path or default_cookie_path()
    path = path.resolve()
    if not path.is_file():
        return {}
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    key = str(path)
    if (
        _file_cache.get("path") == key
        and _file_cache.get("mtime") == mtime
        and "cookies" in _file_cache
    ):
        return dict(_file_cache["cookies"])
    try:
        blob = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    cookies = parse_cookie_blob(blob)
    _file_cache["path"] = key
    _file_cache["mtime"] = mtime
    _file_cache["cookies"] = cookies
    return dict(cookies)


def load_cookies() -> dict[str, str]:
    """合并文件 Cookie + 环境变量 `TENCLIP_XHS_COOKIE`（环境变量覆盖同名键）。"""
    merged = load_cookies_from_file()
    env = os.environ.get("TENCLIP_XHS_COOKIE", "").strip()
    if env:
        merged.update(parse_cookie_blob(env))
    return merged


def cookie_status() -> dict[str, Any]:
    """诊断用：是否找到 Cookie 文件、键数量、常见键是否存在（不返回值）。"""
    path = default_cookie_path()
    cookies = load_cookies()
    return {
        "cookie_file": str(path),
        "cookie_file_exists": path.is_file(),
        "cookie_count": len(cookies),
        "has_a1": "a1" in cookies,
        "has_web_session": "web_session" in cookies,
    }
