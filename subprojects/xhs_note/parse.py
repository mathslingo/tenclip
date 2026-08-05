"""从笔记页 HTML 解析标题、摘要、封面等（内嵌 JSON 优先，meta 为辅）。"""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

_SPURIOUS_TITLE_FRAGMENTS = (
    "用万能旅行拍照姿势美美出片",
    "万能旅行拍照姿势",
    "你的生活兴趣社区",
    "页面不见了",
    "页面不见",
)


def normalize_note_id(note_id: str) -> str:
    nid = note_id.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{24}", nid):
        raise ValueError(f"invalid note_id (expect 24 hex chars): {note_id!r}")
    return nid


def explore_url(note_id: str) -> str:
    return f"https://www.xiaohongshu.com/explore/{normalize_note_id(note_id)}"


def _decode_json_str(inner: str) -> str:
    try:
        return json.loads(f'"{inner}"')
    except json.JSONDecodeError:
        return inner.encode("utf-8", "surrogatepass").decode("unicode_escape", errors="replace")


def is_bad_title(title: str | None) -> bool:
    if not title or not str(title).strip():
        return True
    t = str(title).strip()
    if len(t) < 2:
        return True
    return any(s in t for s in _SPURIOUS_TITLE_FRAGMENTS)


def _meta(html: str, prop: str) -> str:
    esc = re.escape(prop)
    for pat in (
        rf'<meta[^>]+(?:property|name)=["\']{esc}["\'][^>]+content=["\']([^"\']*)["\']',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{esc}["\']',
    ):
        m = re.search(pat, html, flags=re.I)
        if m:
            return unescape(m.group(1)).strip()
    return ""


def _note_window(html: str, note_id: str, before: int = 8000, after: int = 120_000) -> str | None:
    lo, nid = html.lower(), note_id.lower()
    i = lo.find(nid)
    if i < 0:
        return None
    return html[max(0, i - before) : min(len(html), i + after)]


def _title_in_window(html: str, note_id: str, title: str) -> bool:
    win = _note_window(html, note_id, before=12_000, after=80_000)
    if not win or not title:
        return False
    t = title.strip()
    return t in win or t.replace('"', '\\"') in win


def _from_initial_state(html: str, note_id: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {"title": None, "description": None}
    if "__INITIAL_STATE__" not in html:
        return out
    ist = html.find("__INITIAL_STATE__")
    chunk = html[ist : min(len(html), ist + 1_500_000)]
    nid = re.escape(note_id)
    for win in (10_000, 30_000, 60_000):
        m = re.search(
            rf'"{nid}"\s*:\s*\{{[\s\S]{{0,{win}}}?"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            chunk,
            re.I,
        )
        if m:
            t = _decode_json_str(m.group(1)).strip()
            if not is_bad_title(t):
                out["title"] = t
                break
        m2 = re.search(
            rf'"title"\s*:\s*"((?:[^"\\]|\\.)*)"[\s\S]{{0,{win}}}?"{nid}"',
            chunk,
            re.I,
        )
        if not out["title"] and m2:
            t = _decode_json_str(m2.group(1)).strip()
            if not is_bad_title(t):
                out["title"] = t
    dm = re.search(
        rf'"{nid}"\s*:\s*\{{[\s\S]{{0,40000}}?"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
        chunk,
        re.I,
    )
    if dm:
        out["description"] = _decode_json_str(dm.group(1)).strip() or None
    return out


def _from_embedded_json(html: str, note_id: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {"title": None, "description": None}
    blob = html.replace("\\/", "/")
    nid = re.escape(note_id)
    for w in (15_000, 35_000, 70_000):
        for pat in (
            rf'"(?:noteId|note_id)"\s*:\s*"{nid}"[\s\S]{{0,{w}}}?"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            rf'explore/{nid}[\s\S]{{0,{w}}}?"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            rf'"{nid}"[\s\S]{{0,{w}}}?"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            rf'"title"\s*:\s*"((?:[^"\\]|\\.)*)"[\s\S]{{0,{w}}}?"(?:noteId|note_id)"\s*:\s*"{nid}"',
        ):
            m = re.search(pat, blob, re.I)
            if m:
                t = _decode_json_str(m.group(1)).strip()
                if not is_bad_title(t) and "nickName" not in t:
                    out["title"] = t
                    break
        if out["title"]:
            break
    dm = re.search(
        rf'"(?:noteId|note_id)"\s*:\s*"{nid}"[\s\S]{{0,35000}}?"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
        blob,
        re.I,
    )
    if not dm:
        dm = re.search(
            rf'"{nid}"[\s\S]{{0,35000}}?"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
            blob,
            re.I,
        )
    if dm:
        out["description"] = _decode_json_str(dm.group(1)).strip() or None
    return out


def _score_image(url: str) -> int:
    if not url.startswith("http"):
        return -10_000
    u = url.lower()
    if any(x in u for x in ("fe-static", "formula-static", "picasso-static", "avatar", "logo", "favicon")):
        return -5000
    if "sns-webpic" in u or "notes_pre_post" in u:
        return 100
    if "ci.xiaohongshu.com" in u or "pic.xiaohongshu.com" in u:
        return 80
    if "xhscdn.com" in u:
        return 40
    return 10


def _pick_image(candidates: list[str]) -> str | None:
    best: str | None = None
    best_sc = -10_000
    for raw in candidates:
        u = unescape(raw.strip()).strip('"')
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            continue
        sc = _score_image(u)
        if sc > best_sc:
            best_sc, best = sc, u
    return best if best_sc > 0 else None


def _collect_images(html: str, note_id: str) -> list[str]:
    out: list[str] = []
    win = _note_window(html, note_id) or html
    for blob in (win, html):
        b = blob.replace("\\/", "/")
        for m in re.finditer(
            r'https://[a-z0-9-]+\.xhscdn\.com/[^\s"\'<>\\]{12,900}',
            b,
            re.I,
        ):
            out.append(m.group(0))
        for m in re.finditer(r'https://pic\.xiaohongshu\.com/[^\s"\'<>\\]{12,500}', b, re.I):
            out.append(m.group(0))
    og = _meta(html, "og:image:secure_url") or _meta(html, "og:image")
    if og:
        out.append(og)
    return out


def _tags_from_text(text: str | None) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    tags: list[str] = []
    for raw in re.findall(r"#[^\s#]{1,48}", text):
        t = raw.lstrip("#").strip()
        if t and t not in seen:
            seen.add(t)
            tags.append(t)
    return tags[:12]


def parse_note_html(html: str, note_id: str) -> dict[str, Any]:
    """解析单页 HTML，返回 NoteInfo 字段字典。"""
    note_id = normalize_note_id(note_id)
    initial = _from_initial_state(html, note_id)
    embedded = _from_embedded_json(html, note_id)

    title: str | None = None
    for cand in (initial.get("title"), embedded.get("title")):
        if cand and not is_bad_title(cand):
            title = cand
            break
    if not title:
        for cand in (_meta(html, "og:title"), _meta(html, "twitter:title")):
            if cand and not is_bad_title(cand) and _title_in_window(html, note_id, cand):
                title = cand
                break

    description: str | None = None
    for cand in (initial.get("description"), embedded.get("description")):
        if cand and str(cand).strip():
            description = str(cand).strip()
            break
    if not description:
        for cand in (_meta(html, "og:description"), _meta(html, "twitter:description")):
            if cand and str(cand).strip():
                description = str(cand).strip()
                break

    image_url = _pick_image(_collect_images(html, note_id))
    tags = _tags_from_text(description) + _tags_from_text(title)
    seen: set[str] = set()
    uniq_tags: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq_tags.append(t)

    return {
        "note_id": note_id,
        "explore_url": explore_url(note_id),
        "title": title,
        "description": description,
        "image_url": image_url,
        "tags": uniq_tags,
        "likes": _meta(html, "og:xhs:note_like") or None,
        "note_type": _meta(html, "og:xhs:note_type") or None,
    }
