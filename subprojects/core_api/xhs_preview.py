"""抓取小红书笔记页元数据：仅用 requests + 标准库解析 HTML。

优先使用页面中的 **Open Graph**、**Twitter Card**、**ld+json** 与内嵌 JSON 片段（标题、正文摘要、封面），
无需登录 Cookie 即可在多数笔记上工作。

支持从 **`/search_result`** 搜索页 HTML 中解析笔记 id（`/explore/{id}`、`noteId` 等），再并行复用笔记页解析逻辑拉取 meta。

可选：若遇风控页仍解析失败，可配置 `TENCLIP_XHS_COOKIE` / `TENCLIP_XHS_COOKIE_FILE` /
`data/xhs_cookie.txt`（见 `_merged_cookie_dict`），以登录态再拉一次。"""

from __future__ import annotations

import asyncio
import json
import os
import re
from html import unescape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlencode, urlunparse, urlparse

import requests
from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

ALLOWED_HOSTS = frozenset({"www.xiaohongshu.com", "xiaohongshu.com"})
ALLOWED_PREFIXES = ("/explore/", "/discovery/item/")

# 小红书对无 Cookie / 机房 IP 常返回 200 +「页面不见了」，OG 里仍是「标题」——需识别并换源解析
_WALL_SUBSTR = (
    "页面不见了",
    "页面不见",
    "你访问的页面",
    "访问的页面",
    "请通过验证",
    "安全验证",
    "登录后查看",
    "登录查看",
    "验证",
)

# 壳站/推荐位常出现在 og:title，canonical 仍带 note_id 时也会误用
_SPURIOUS_TITLE_SUBSTR = (
    "用万能旅行拍照姿势美美出片",
    "万能旅行拍照姿势",
    "你的生活兴趣社区",
)


def _coerce_note_url(raw: str) -> str:
    """校验并规范化笔记 URL；失败时抛出 ValueError（供批量接口按条处理）。"""
    u = unquote(raw.strip())
    if len(u) > 4096:
        raise ValueError("url too long")
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http(s) URLs")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError("only xiaohongshu.com URLs are allowed")
    path = parsed.path or ""
    if not any(path.startswith(p) for p in ALLOWED_PREFIXES):
        raise ValueError("only /explore/ or /discovery/item/ note URLs")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _validate_note_url(raw: str) -> str:
    try:
        return _coerce_note_url(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _note_id_from_path(url: str) -> str | None:
    path = (urlparse(url).path or "").rstrip("/")
    if not path:
        return None
    return path.split("/")[-1]


def _explore_url_from_note_id(note_id: str) -> str | None:
    nid = note_id.strip().lower()
    if re.fullmatch(r"[0-9a-f]{24}", nid):
        return f"https://www.xiaohongshu.com/explore/{nid}"
    return None


def _coerce_search_url(raw: str) -> str:
    """校验搜索页 URL（须含 /search_result，保留 query）。"""
    u = raw.strip()
    if len(u) > 4096:
        raise ValueError("search url too long")
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http(s) URLs")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError("only xiaohongshu.com URLs are allowed")
    path = parsed.path or ""
    if not path.startswith("/search_result"):
        raise ValueError("only /search_result URLs")
    return u


def _validate_search_url(raw: str) -> str:
    try:
        return _coerce_search_url(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _search_url_from_keyword(keyword: str) -> str:
    q = keyword.strip()
    if not q:
        raise ValueError("keyword is empty")
    if len(q) > 120:
        raise ValueError("keyword too long")
    return "https://www.xiaohongshu.com/search_result?" + urlencode(
        {"keyword": q, "source": "web_explore_feed", "type": "51"}
    )


def _extract_note_ids_from_html(html: str, limit: int) -> list[str]:
    """从搜索页 / 列表页 HTML 中收集 explore 或 discovery 笔记 id（24 位 hex），保序去重。"""
    seen: set[str] = set()
    out: list[str] = []

    def add(nid: str) -> None:
        n = nid.lower()
        if len(n) != 24 or not re.fullmatch(r"[0-9a-f]{24}", n):
            return
        if n not in seen:
            seen.add(n)
            out.append(n)

    blob = html.replace("\\/", "/")
    patterns = (
        r'https?://(?:www\.)?xiaohongshu\.com/explore/([0-9a-f]{24})(?:["\s?<>]|$)',
        r'https?://(?:www\.)?xiaohongshu\.com/discovery/item/([0-9a-f]{24})(?:["\s?<>]|$)',
        r'["\']/explore/([0-9a-f]{24})(?:["\s?<>]|$)',
        r'["\']/discovery/item/([0-9a-f]{24})(?:["\s?<>]|$)',
        r'"noteId"\s*:\s*"([0-9a-f]{24})"',
        r'"note_id"\s*:\s*"([0-9a-f]{24})"',
    )
    for pat in patterns:
        for m in re.finditer(pat, blob, flags=re.I):
            add(m.group(1))
            if len(out) >= limit:
                return out
    return out


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_semicolon_cookies(raw: str) -> dict[str, str]:
    """解析 `a1=...; web_session=...` 形式的 Cookie 串。"""
    out: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                out[k] = v
    return out


def _parse_netscape_cookie_file(raw: str) -> dict[str, str]:
    """解析浏览器导出的 Netscape cookie 文件（制表符分隔）。"""
    out: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            name, value = parts[5], parts[6]
            if name:
                out[name] = value
    return out


def _parse_cookie_blob(raw: str) -> dict[str, str]:
    raw = raw.strip()
    if not raw:
        return {}
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    for line in raw.splitlines():
        ls = line.strip()
        if not ls or ls.startswith("#"):
            continue
        if ls.count("\t") >= 6:
            return _parse_netscape_cookie_file(raw)
        break
    return _parse_semicolon_cookies(raw)


_cookie_file_state: dict[str, Any] = {}


def _cookies_from_file() -> dict[str, str]:
    """读取 TENCLIP_XHS_COOKIE_FILE 或默认 `data/xhs_cookie.txt`（按 mtime 缓存）。"""
    path = os.environ.get("TENCLIP_XHS_COOKIE_FILE", "").strip()
    if not path:
        path = str(_repo_root() / "data" / "xhs_cookie.txt")
    if not os.path.isfile(path):
        return {}
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    if (
        _cookie_file_state.get("path") == path
        and _cookie_file_state.get("mtime") == mtime
        and "cookies" in _cookie_file_state
    ):
        return _cookie_file_state["cookies"]
    try:
        blob = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    cookies = _parse_cookie_blob(blob)
    _cookie_file_state["path"] = path
    _cookie_file_state["mtime"] = mtime
    _cookie_file_state["cookies"] = cookies
    return cookies


def _merged_cookie_dict() -> dict[str, str] | None:
    """文件中的 Cookie 优先，环境变量 TENCLIP_XHS_COOKIE 覆盖同名项（便于临时覆盖）。

    设置 `TENCLIP_XHS_NO_COOKIE=1` 时忽略文件与环境中的 Cookie（用于脚本校验无登录态抓取）。
    """
    if os.environ.get("TENCLIP_XHS_NO_COOKIE", "").strip().lower() in ("1", "true", "yes"):
        return None
    merged: dict[str, str] = {}
    merged.update(_cookies_from_file())
    env = os.environ.get("TENCLIP_XHS_COOKIE", "").strip()
    if env:
        merged.update(_parse_cookie_blob(env))
    return merged or None


def _browser_headers(_url: str, mobile: bool) -> dict[str, str]:
    if mobile:
        ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
        )
    else:
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        )
    h: dict[str, str] = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Cache-Control": "no-cache",
        "Origin": "https://www.xiaohongshu.com",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    if not mobile:
        h["sec-ch-ua"] = '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"'
        h["sec-ch-ua-mobile"] = "?0"
        h["sec-ch-ua-platform"] = '"Windows"'
    h["Referer"] = _url if _url.startswith("http") else "https://www.xiaohongshu.com/"
    return h


def _is_bot_wall(title: str | None, description: str | None) -> bool:
    if not title or not str(title).strip():
        return True
    t = str(title).strip()
    d = (description or "").strip()
    blob = t + d
    for s in _WALL_SUBSTR:
        if s in t or s in d:
            return True
    if t in ("小红书", "Xiaohongshu", "小红书 - 你的生活兴趣社区"):
        return True
    if "小红书" in t and ("不见" in t or "访问" in t or "验证" in t):
        return True
    if len(t) < 6 and "小红书" in blob:
        return True
    for s in _SPURIOUS_TITLE_SUBSTR:
        if s in t:
            return True
    return False


def _is_spurious_note_title(title: str | None) -> bool:
    if not title or not str(title).strip():
        return True
    return _is_bot_wall(str(title).strip(), None)


def _note_id_html_window(html: str, note_id: str, before: int = 6000, after: int = 90_000) -> str | None:
    if not note_id:
        return None
    lo, nid = html.lower(), note_id.lower()
    idx = lo.find(nid)
    if idx == -1:
        return None
    return html[max(0, idx - before) : min(len(html), idx + after)]


def _title_in_note_window(html: str, note_id: str | None, title: str) -> bool:
    """标题是否出现在当前 note_id 附近的内嵌 JSON 中（而非仅 head og）。"""
    if not note_id or not title or not title.strip():
        return False
    win = _note_id_html_window(html, note_id)
    if not win:
        return False
    t = title.strip()
    if t in win:
        return True
    esc = t.replace("\\", "\\\\").replace('"', '\\"')
    return esc in win


def _meta_property(html: str, prop: str) -> str | None:
    esc = re.escape(prop)
    patterns = (
        rf'<meta\s[^>]*property=["\']{esc}["\'][^>]*content=["\']([^"\']*)["\']',
        rf'<meta\s[^>]*content=["\']([^"\']*)["\'][^>]*property=["\']{esc}["\']',
    )
    for pat in patterns:
        m = re.search(pat, html, flags=re.I | re.DOTALL)
        if m:
            val = unescape(m.group(1)).strip()
            if val:
                return val
    return None


def _meta_name(html: str, name: str) -> str | None:
    esc = re.escape(name)
    patterns = (
        rf'<meta\s[^>]*name=["\']{esc}["\'][^>]*content=["\']([^"\']*)["\']',
        rf'<meta\s[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']{esc}["\']',
    )
    for pat in patterns:
        m = re.search(pat, html, flags=re.I | re.DOTALL)
        if m:
            val = unescape(m.group(1)).strip()
            if val:
                return val
    return None


def _head_meta_claims_current_note(html: str, note_id: str | None) -> bool:
    """canonical / og:url 是否指向当前笔记 id；为 False 时 head 里的 og/twitter 常为壳站或别篇，不可信。"""
    if not note_id:
        return True
    nid = note_id.lower()
    og_url = _meta_property(html, "og:url")
    if og_url and nid in og_url.lower():
        return True
    tw_url = _meta_name(html, "twitter:url")
    if tw_url and nid in tw_url.lower():
        return True
    m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if m and nid in m.group(1).lower():
        return True
    m = re.search(
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']',
        html,
        re.I,
    )
    if m and nid in m.group(1).lower():
        return True
    return False


def _tags_from_text(text: str | None, limit: int = 8) -> list[str]:
    if not text:
        return []
    found = re.findall(r"#[^\s#]{1,48}", text)
    out: list[str] = []
    seen: set[str] = set()
    for raw in found:
        t = raw.lstrip("#").strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= limit:
            break
    return out


def _fallback_title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>([^<]{1,500})</title>", html, flags=re.I | re.DOTALL)
    if not m:
        return None
    t = unescape(m.group(1)).strip()
    for suf in (" - 小红书", " - 小红书社区", " | 小红书"):
        if t.endswith(suf):
            t = t[: -len(suf)].strip()
    return t or None


def _is_likely_avatar_or_brand_ui(url: str) -> bool:
    u = url.lower()
    needles = (
        "avatar",
        "/user/",
        "profile.",
        "fe-platform",
        "picasso-static.xhscdn.com/fe",
        "fe-static.xhscdn.com",
        "formula-static",
        "/ranchi/",
        "logo",
        "icon_",
        "favicon",
    )
    return any(n in u for n in needles)


def _score_cover_url(url: str) -> int:
    """分数越高越像笔记封面（视频首帧 / image_list）。"""
    if not url or not url.startswith("http"):
        return -10_000
    u = url.lower()
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".xhscdn.com") and "sns-video" in host:
        return -2500
    if any(x in u for x in (".m3u8", "video/tos")):
        return -2500
    if _is_likely_avatar_or_brand_ui(url):
        return -2000
    s = 0
    if "pic.xiaohongshu.com" in u:
        s += 42
    if "sns-webpic-qc" in url:
        s += 50
    if "notes_pre_post" in url or "/note/" in url.lower():
        s += 45
    if "spectrum" in url:
        s += 15
    if "ci.xiaohongshu.com" in url:
        s += 30
    if "sns-img-" in url and "xhscdn.com" in url:
        s += 25
    if "webp" in url.lower() or "jpg" in url.lower() or "jpeg" in url.lower():
        s += 5
    if "imageview" in url.lower() or "format/" in url.lower():
        s += 12
    s += min(len(url) // 25, 20)
    return s


def _pick_best_cover_url(candidates: Iterable[str | None]) -> str | None:
    best: str | None = None
    best_sc = -10_000
    for raw in candidates:
        if not raw:
            continue
        u = unescape(str(raw).strip().strip('"'))
        if not u.startswith("http"):
            continue
        sc = _score_cover_url(u)
        if sc > best_sc:
            best_sc, best = sc, u
    if best is None or best_sc < -350:
        return None
    return best


def _note_id_window(html: str, note_id: str | None, before: int = 4000, after: int = 72_000) -> str | None:
    """当前笔记 id 在 HTML 中的大致窗口，用于封面/内嵌字段，弱化整页推荐流噪声。"""
    if not note_id:
        return None
    lo, nid = html.lower(), note_id.lower()
    idx = lo.find(nid)
    if idx == -1:
        return None
    return html[max(0, idx - before) : min(len(html), idx + after)]


def _collect_cover_url_strings(html: str, note_id: str | None = None) -> list[str]:
    """从整页 HTML 收集可能的封面 URL；优先扫描 note_id 窗口再扫全页。"""
    out: list[str] = []

    def _add(u: str | None) -> None:
        if u and u.startswith("http"):
            out.append(u)

    def _add_json_url_field(inner: str) -> None:
        raw = _decode_json_string_inner(inner).strip()
        if not raw.startswith("http"):
            return
        _add(unescape(raw))

    blobs: list[str] = []
    w = _note_id_window(html, note_id)
    if w:
        blobs.append(w)
    blobs.append(html)

    for blob in blobs:
        for m in re.finditer(r'"type"\s*:\s*"video"', blob):
            chunk = blob[m.start() : m.start() + 55_000]
            for um in re.finditer(
                r'"(?:url|urlDefault|url_default|first_frame|thumbUrl|thumb_url)"\s*:\s*"((?:[^"\\]|\\.)*)"',
                chunk,
            ):
                _add_json_url_field(um.group(1))
            for um in re.finditer(
                r'"cover"\s*:\s*\{[\s\S]{0,4000}?"url"\s*:\s*"((?:[^"\\]|\\.)*)"',
                chunk,
                flags=re.DOTALL,
            ):
                _add_json_url_field(um.group(1))

        for m in re.finditer(r'"imageList"\s*:\s*\[', blob):
            chunk = blob[m.start() : m.start() + 35_000]
            for um in re.finditer(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', chunk):
                _add_json_url_field(um.group(1))
            for um in re.finditer(
                r'"originUrl"\s*:\s*"((?:[^"\\]|\\.)*)"',
                chunk,
            ):
                _add_json_url_field(um.group(1))

        blob_sl = blob.replace("\\/", "/")
        for m in re.finditer(
            r'https://[a-z0-9-]+\.xhscdn\.com/[^\s"\'<>\\]{8,900}',
            blob_sl,
            flags=re.I,
        ):
            raw = m.group(0).rstrip("\\").rstrip(",").rstrip('"').rstrip("'")
            _add(raw)
        for m in re.finditer(r'https://pic\.xiaohongshu\.com/[^\s"\'<>\\]{8,500}', blob_sl, flags=re.I):
            _add(m.group(0).rstrip("\\").rstrip(",").rstrip('"').rstrip("'"))
        for m in re.finditer(r'https://ci\.xiaohongshu\.com/[^\s"\'<>\\]{8,800}', blob_sl, flags=re.I):
            _add(m.group(0).rstrip("\\").rstrip(",").rstrip('"').rstrip("'"))

    seen: set[str] = set()
    uniq: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq[:120]


def _parse_ld_json(html: str, note_id: str | None) -> dict[str, str | None]:
    out: dict[str, str | None] = {"title": None, "image": None, "description": None}
    for m in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
        html,
        re.I,
    ):
        raw = m.group(1).strip()
        if not raw.startswith("{"):
            continue
        if note_id:
            nid = note_id.lower()
            rlo = raw.lower()
            if nid not in rlo and f"explore/{nid}" not in rlo and f"discovery/item/{nid}" not in rlo:
                continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for obj in items:
            if not isinstance(obj, dict):
                continue
            typ = obj.get("@type")
            types = typ if isinstance(typ, list) else ([typ] if typ else [])
            type_str = " ".join(str(t) for t in types if t)
            if "VideoObject" in type_str:
                if note_id and not _ld_object_references_note(obj, note_id):
                    continue
                out["title"] = out["title"] or obj.get("name")
                img = obj.get("thumbnailUrl") or obj.get("image")
                if isinstance(img, list) and img:
                    img = img[0]
                if isinstance(img, str):
                    out["image"] = out["image"] or img
                out["description"] = out["description"] or obj.get("description")
            elif "Article" in type_str or "SocialMediaPosting" in type_str:
                if note_id and not _ld_object_references_note(obj, note_id):
                    continue
                out["title"] = out["title"] or obj.get("headline") or obj.get("name")
                img = obj.get("image")
                if isinstance(img, dict):
                    img = img.get("url")
                if isinstance(img, list) and img:
                    img = img[0]
                if isinstance(img, str):
                    out["image"] = out["image"] or img
                out["description"] = out["description"] or obj.get("description")
    return out


def _decode_json_string_inner(inner: str) -> str:
    """将 JSON 字符串字面量的内部片段解码为 Python str。"""
    try:
        return json.loads(f'"{inner}"')
    except json.JSONDecodeError:
        return inner.encode("utf-8", "surrogatepass").decode("unicode_escape", errors="replace")


def _ld_object_references_note(obj: dict[str, Any], note_id: str) -> bool:
    """ld+json 里同一段可能有多个 VideoObject，只采纳 URL/@id 含当前笔记 id 的对象。"""
    nid = note_id.lower()
    for k in ("url", "embedUrl", "@id", "mainEntityOfPage", "identifier"):
        v = obj.get(k)
        if isinstance(v, str) and nid in v.lower():
            return True
        if isinstance(v, dict):
            u = v.get("@id") or v.get("url")
            if isinstance(u, str) and nid in u.lower():
                return True
    return False


def _extract_initial_state_by_note_id(html: str, note_id: str | None) -> dict[str, str | None]:
    """从 window.__INITIAL_STATE__ 大块 JSON 中按 note_id 抠 title/desc。"""
    out: dict[str, str | None] = {"title": None, "description": None}
    if not note_id or "__INITIAL_STATE__" not in html:
        return out
    ist = html.find("__INITIAL_STATE__")
    chunk = html[ist : min(len(html), ist + 1_200_000)]
    nid_esc = re.escape(note_id)
    for win in (8_000, 20_000, 50_000):
        tm = re.search(
            rf'"{nid_esc}"\s*:\s*\{{[\s\S]{{0,{win}}}?"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            chunk,
            flags=re.I,
        )
        if tm:
            t = _decode_json_string_inner(tm.group(1)).strip()
            if t and not _is_spurious_note_title(t):
                out["title"] = t
                break
        tm2 = re.search(
            rf'"title"\s*:\s*"((?:[^"\\]|\\.)*)"[\s\S]{{0,{win}}}?"{nid_esc}"',
            chunk,
            flags=re.I,
        )
        if not out["title"] and tm2:
            t = _decode_json_string_inner(tm2.group(1)).strip()
            if t and not _is_spurious_note_title(t):
                out["title"] = t
    dm = re.search(
        rf'"{nid_esc}"\s*:\s*\{{[\s\S]{{0,30000}}?"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
        chunk,
        flags=re.I,
    )
    if dm:
        out["description"] = _decode_json_string_inner(dm.group(1)).strip() or None
    return out


def _extract_note_fields_by_note_id(html: str, note_id: str | None) -> dict[str, str | None]:
    """在含 noteId / explore/{id} 的 JSON 片段上抠 title/desc。"""
    out: dict[str, str | None] = {"title": None, "description": None}
    if not note_id:
        return out
    nid_esc = re.escape(note_id)
    blob = html.replace("\\/", "/")
    for w in (12_000, 28_000, 55_000):
        for pat in (
            rf'"(?:noteId|note_id)"\s*:\s*"{nid_esc}"[\s\S]{{0,{w}}}?"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            rf"explore/{nid_esc}[\s\S]{{0,{w}}}?\"title\"\s*:\s*\"((?:[^\"\\\\]|\\\\.)*)\"",
            rf'"{nid_esc}"[\s\S]{{0,{w}}}?"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            rf'"title"\s*:\s*"((?:[^"\\]|\\.)*)"[\s\S]{{0,{w}}}?"(?:noteId|note_id)"\s*:\s*"{nid_esc}"',
            rf'"title"\s*:\s*"((?:[^"\\]|\\.)*)"[\s\S]{{0,{w}}}?explore/{nid_esc}',
        ):
            tm = re.search(pat, blob, flags=re.I)
            if tm:
                t = _decode_json_string_inner(tm.group(1)).strip()
                if t and not _is_spurious_note_title(t) and "nickName" not in t:
                    out["title"] = t
                    break
        if out["title"]:
            break
    dm = re.search(
        rf'"(?:noteId|note_id)"\s*:\s*"{nid_esc}"[\s\S]{{0,28000}}?"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
        blob,
        flags=re.I,
    )
    if not dm:
        dm = re.search(
            rf'"{nid_esc}"[\s\S]{{0,28000}}?"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
            blob,
            flags=re.I,
        )
    if dm:
        out["description"] = _decode_json_string_inner(dm.group(1)).strip() or None
    return out


def _extract_video_note_from_html(html: str, note_id: str | None) -> dict[str, str | None]:
    """从含当前笔记 id 的 HTML 片段中抠 video 的 title / desc，避免命中推荐流里第一篇「假 video」。"""
    out: dict[str, str | None] = {"title": None, "description": None}
    scope = html
    if note_id:
        lo = html.lower()
        nid = note_id.lower()
        idx = lo.find(nid)
        if idx != -1:
            scope = html[max(0, idx - 4000) : min(len(html), idx + 48_000)]
        else:
            # 无 id 锚点：不用全文首个 video（多为壳站推荐）
            scope = ""

    if scope:
        vm = re.search(
            r'"type"\s*:\s*"video"[\s\S]{0,3500}?"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            scope,
        )
        if vm:
            out["title"] = _decode_json_string_inner(vm.group(1))
        dm = re.search(
            r'"type"\s*:\s*"video"[\s\S]{0,3500}?"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
            scope,
        )
        if dm:
            out["description"] = _decode_json_string_inner(dm.group(1))
        if note_id and not out["title"]:
            idx2 = scope.lower().find(note_id.lower())
            if idx2 != -1:
                chunk = scope[idx2 : idx2 + 28_000]
                for m in re.finditer(r'"title"\s*:\s*"((?:[^"\\]|\\.){4,400})"', chunk):
                    cand = _decode_json_string_inner(m.group(1)).strip()
                if cand and not _is_spurious_note_title(cand) and "nickName" not in cand:
                    out["title"] = cand
                    break
    return out


def _normalize_image_url(img: str | None) -> str | None:
    if not isinstance(img, str):
        return None
    img = img.strip()
    if not img:
        return None
    if img.startswith("//"):
        return "https:" + img
    if img.startswith("/"):
        return "https://www.xiaohongshu.com" + img
    return img


def _build_meta(html: str, note_id: str | None) -> dict[str, Any]:
    head_ok = _head_meta_claims_current_note(html, note_id)
    og_title = (_meta_property(html, "og:title") if head_ok else None)
    og_desc = (_meta_property(html, "og:description") if head_ok else None)
    og_image = (
        (_meta_property(html, "og:image:secure_url") or _meta_property(html, "og:image")) if head_ok else None
    )
    tw_title = (_meta_name(html, "twitter:title") if head_ok else None)
    tw_desc = (_meta_name(html, "twitter:description") if head_ok else None)
    tw_image = (_meta_name(html, "twitter:image") if head_ok else None)

    initial = _extract_initial_state_by_note_id(html, note_id)
    ld = _parse_ld_json(html, note_id)
    emb = _extract_video_note_from_html(html, note_id)
    anchored = _extract_note_fields_by_note_id(html, note_id)
    page_covers = _collect_cover_url_strings(html, note_id)

    title: str | None = None
    title_cands: list[str | None] = [
        initial.get("title"),
        anchored.get("title"),
        emb.get("title"),
        ld.get("title"),
    ]
    if head_ok:
        for og in (tw_title, og_title):
            if og and not _is_spurious_note_title(og) and _title_in_note_window(html, note_id, str(og)):
                title_cands.append(str(og).strip())
        ft = _fallback_title(html)
        if ft and not _is_spurious_note_title(ft) and _title_in_note_window(html, note_id, ft):
            title_cands.append(ft)
    for cand in title_cands:
        if cand and str(cand).strip() and not _is_spurious_note_title(str(cand)):
            title = str(cand).strip()
            break

    description: str | None = None
    desc_cands: list[str | None] = [
        initial.get("description"),
        anchored.get("description"),
        emb.get("description"),
        ld.get("description"),
    ]
    if head_ok:
        desc_cands += (tw_desc, og_desc)
    for cand in desc_cands:
        if not cand or not str(cand).strip():
            continue
        cs = str(cand).strip()
        if not _is_bot_wall(None, cs):
            description = cs
            break
    if not description:
        for cand in desc_cands:
            if cand and str(cand).strip():
                description = str(cand).strip()
                break

    cover_cands: list[str | None] = [ld.get("image"), *page_covers]
    if head_ok:
        cover_cands = [ld.get("image"), tw_image, og_image, *page_covers]

    meta: dict[str, Any] = {
        "title": title,
        "image": _normalize_image_url(_pick_best_cover_url(cover_cands)),
        "description": description,
        "tags": [],
    }

    tags = _tags_from_text(meta.get("description")) + _tags_from_text(meta.get("title"))
    seen: set[str] = set()
    uniq: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    meta["tags"] = uniq[:12]
    return meta


def _fetch_html_sync(url: str, mobile: bool) -> str:
    """使用 requests 拉取 HTML；Cookie 为可选（见 _merged_cookie_dict）。"""
    cookies = _merged_cookie_dict()
    headers = _browser_headers(url, mobile=mobile)
    try:
        r = requests.get(
            url,
            headers=headers,
            cookies=cookies or {},
            timeout=22,
            allow_redirects=True,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"fetch failed: {e}") from e
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"upstream returned {r.status_code}")
    return r.text


async def _get_html(url: str, mobile: bool) -> str:
    return await asyncio.to_thread(_fetch_html_sync, url, mobile)


async def fetch_xhs_note_preview(url: str) -> dict[str, Any]:
    note_id = _note_id_from_path(url)
    html = await _get_html(url, mobile=False)
    meta = _build_meta(html, note_id)
    if _is_bot_wall(meta.get("title"), meta.get("description")) or _is_spurious_note_title(
        meta.get("title")
    ):
        html_m = await _get_html(url, mobile=True)
        meta_m = _build_meta(html_m, note_id)
        if (
            not _is_bot_wall(meta_m.get("title"), meta_m.get("description"))
            and not _is_spurious_note_title(meta_m.get("title"))
        ) or meta_m.get("image"):
            meta = meta_m
    if _is_bot_wall(meta.get("title"), meta.get("description")) or _is_spurious_note_title(
        meta.get("title")
    ):
        raise HTTPException(
            status_code=422,
            detail="未能从该笔记页解析出有效标题或摘要（可能为验证页、已删除或页面结构已变更）。"
            "可稍后重试；若仍失败可配置可选 Cookie：TENCLIP_XHS_COOKIE 或 data/xhs_cookie.txt。",
        )
    if not meta.get("title") and not meta.get("image"):
        raise HTTPException(
            status_code=422,
            detail="未能解析到笔记标题或封面；可检查 URL 是否为有效 explore 笔记，或稍后重试。",
        )
    meta["body"] = meta.get("description")
    return meta


_XHS_BATCH_MAX = 24
# 搜索页 HTML 中最多抠出这么多 id，再从中取子集去拉笔记 meta
_SEARCH_ID_EXTRACT_MAX = 48


class XhsNoteBatchRequest(BaseModel):
    """并行抓取多条笔记；`note_ids` 与 `urls` 可混用，合计不超过上限。"""

    note_ids: list[str] = Field(default_factory=list, description="explore 路径最后一段，24 位 hex")
    urls: list[str] = Field(default_factory=list, description="完整笔记 https URL")


async def _fetch_xhs_note_preview_item(url: str) -> dict[str, Any]:
    try:
        data = await fetch_xhs_note_preview(url)
        return {"url": url, **data}
    except HTTPException as e:
        detail = e.detail
        msg = detail if isinstance(detail, str) else str(detail)
        return {
            "url": url,
            "title": None,
            "image": None,
            "description": None,
            "tags": [],
            "error": msg,
        }
    except Exception as e:
        return {
            "url": url,
            "title": None,
            "image": None,
            "description": None,
            "tags": [],
            "error": str(e),
        }


async def fetch_xhs_note_previews_batch(body: XhsNoteBatchRequest) -> dict[str, Any]:
    targets: list[str] = []
    for nid in body.note_ids:
        u = _explore_url_from_note_id(nid)
        if not u:
            raise HTTPException(status_code=400, detail=f"invalid note_id: {nid!r}")
        targets.append(u)
    for raw in body.urls:
        try:
            targets.append(_coerce_note_url(raw))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if len(targets) > _XHS_BATCH_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"at most {_XHS_BATCH_MAX} items combined (note_ids + urls)",
        )
    if not targets:
        raise HTTPException(status_code=400, detail="provide note_ids and/or urls")
    items = await asyncio.gather(*(_fetch_xhs_note_preview_item(u) for u in targets))
    return {"items": list(items)}


async def fetch_xhs_search_note_ids(
    keyword: str | None,
    search_url: str | None,
    limit: int,
) -> dict[str, Any]:
    if limit < 1 or limit > _SEARCH_ID_EXTRACT_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"limit must be 1..{_SEARCH_ID_EXTRACT_MAX}",
        )
    if search_url and search_url.strip():
        try:
            u = _coerce_search_url(search_url.strip())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    elif keyword and keyword.strip():
        try:
            u = _search_url_from_keyword(keyword.strip())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        raise HTTPException(status_code=400, detail="provide keyword or search_url")
    html = await _get_html(u, mobile=False)
    ids = _extract_note_ids_from_html(html, limit)
    if not ids:
        html = await _get_html(u, mobile=True)
        ids = _extract_note_ids_from_html(html, limit)
    return {"note_ids": ids, "search_url": u}


async def fetch_xhs_search_previews(
    keyword: str | None,
    search_url: str | None,
    preview_limit: int,
) -> dict[str, Any]:
    if preview_limit < 1 or preview_limit > _XHS_BATCH_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"preview_limit must be 1..{_XHS_BATCH_MAX}",
        )
    id_cap = min(max(preview_limit * 3, preview_limit), _SEARCH_ID_EXTRACT_MAX)
    pack = await fetch_xhs_search_note_ids(keyword, search_url, id_cap)
    ids = pack["note_ids"]
    if not ids:
        raise HTTPException(
            status_code=422,
            detail="搜索结果页中未解析到笔记 id；可能为空结果、验证页或页面结构已变更；可换关键词或配置可选 Cookie 后重试。",
        )
    to_fetch = ids[:preview_limit]
    batch = await fetch_xhs_note_previews_batch(XhsNoteBatchRequest(note_ids=to_fetch, urls=[]))
    return {
        **batch,
        "search_url": pack["search_url"],
        "note_ids": ids,
    }


def register_xhs_preview_routes(application) -> None:
    """同时注册带/不带 /api 前缀的路径，兼容 Vite 代理是否 rewrite 掉 /api 前缀。"""

    @application.get("/api/utils/xhs-note-preview")
    @application.get("/utils/xhs-note-preview")
    async def xhs_note_preview(url: str = Query(..., min_length=10, max_length=4096)):
        safe = _validate_note_url(url)
        return await fetch_xhs_note_preview(safe)

    @application.post("/api/utils/xhs-note-previews")
    @application.post("/utils/xhs-note-previews")
    async def xhs_note_previews_batch(body: XhsNoteBatchRequest):
        return await fetch_xhs_note_previews_batch(body)

    @application.get("/api/utils/xhs-search-note-ids")
    @application.get("/utils/xhs-search-note-ids")
    async def xhs_search_note_ids(
        keyword: str | None = Query(None, max_length=120),
        search_url: str | None = Query(None, max_length=4096),
        limit: int = Query(24, ge=1, le=48),
    ):
        return await fetch_xhs_search_note_ids(keyword, search_url, limit)

    @application.get("/api/utils/xhs-search-previews")
    @application.get("/utils/xhs-search-previews")
    async def xhs_search_previews(
        keyword: str | None = Query(None, max_length=120),
        search_url: str | None = Query(None, max_length=4096),
        preview_limit: int = Query(12, ge=1, le=24),
    ):
        return await fetch_xhs_search_previews(keyword, search_url, preview_limit)

    from fastapi import Depends
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from . import models as _models
    from .db import get_db

    @application.get("/api/utils/xhs-cached-notes")
    @application.get("/utils/xhs-cached-notes")
    def list_xhs_cached_notes(
        db: Session = Depends(get_db),
        limit: int = Query(50, ge=1, le=200),
    ):
        stmt = (
            select(_models.XhsCachedNote)
            .order_by(_models.XhsCachedNote.fetched_at.desc())
            .limit(limit)
        )
        rows = db.scalars(stmt).all()
        return {
            "items": [
                {
                    "note_id": r.note_id,
                    "explore_url": r.explore_url,
                    "title": r.title,
                    "body": r.body,
                    "image_url": r.image_url,
                    "tags_json": r.tags_json,
                    "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
                }
                for r in rows
            ]
        }
