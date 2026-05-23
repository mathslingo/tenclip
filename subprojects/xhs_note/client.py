"""HTTP 拉取 + Cookie，按笔记 ID 返回 NoteInfo。"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .cookies import load_cookies
from .models import NoteFetchError, NoteInfo
from .parse import explore_url, normalize_note_id, parse_note_html

_SESSION: requests.Session | None = None

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)


def _headers(url: str, mobile: bool) -> dict[str, str]:
    ua = _MOBILE_UA if mobile else _DESKTOP_UA
    h = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Referer": url,
        "Origin": "https://www.xiaohongshu.com",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }
    if not mobile:
        h["sec-ch-ua"] = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
        h["sec-ch-ua-mobile"] = "?0"
        h["sec-ch-ua-platform"] = '"Windows"'
    return h


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
    return _SESSION


def fetch_note_html(note_id: str, *, mobile: bool = False, timeout: float = 25.0) -> str:
    """拉取 explore 页 HTML（自动带 Cookie）。"""
    note_id = normalize_note_id(note_id)
    url = explore_url(note_id)
    cookies = load_cookies()
    if not cookies:
        raise NoteFetchError(
            note_id,
            "未加载到 Cookie：请在 data/xhs_cookie.txt 粘贴浏览器 Cookie，或设置 TENCLIP_XHS_COOKIE",
        )
    try:
        r = _session().get(
            url,
            headers=_headers(url, mobile),
            cookies=cookies,
            timeout=timeout,
            allow_redirects=True,
        )
    except requests.RequestException as e:
        raise NoteFetchError(note_id, f"请求失败: {e}") from e
    if r.status_code != 200:
        raise NoteFetchError(note_id, f"HTTP {r.status_code}", status_code=r.status_code)
    return r.text


def fetch_note_by_id(note_id: str, *, try_mobile_fallback: bool = True) -> NoteInfo:
    """
    根据 24 位笔记 ID 获取基本信息。

    优先桌面 UA；若无有效标题且 `try_mobile_fallback`，再试移动 UA。
    """
    note_id = normalize_note_id(note_id)
    html = fetch_note_html(note_id, mobile=False)
    fields = parse_note_html(html, note_id)

    if try_mobile_fallback and not fields.get("title") and not fields.get("image_url"):
        html_m = fetch_note_html(note_id, mobile=True)
        fields_m = parse_note_html(html_m, note_id)
        if fields_m.get("title") or fields_m.get("image_url"):
            fields = fields_m

    info = NoteInfo(
        note_id=fields["note_id"],
        explore_url=fields["explore_url"],
        title=fields.get("title"),
        description=fields.get("description"),
        image_url=fields.get("image_url"),
        tags=list(fields.get("tags") or []),
        likes=fields.get("likes"),
        note_type=fields.get("note_type"),
    )
    if not info.title and not info.image_url:
        if "页面不见了" in html or "你访问的页面" in html:
            raise NoteFetchError(note_id, "页面不存在或 Cookie 已失效（页面不见了）")
        raise NoteFetchError(
            note_id,
            "未能解析到标题或封面；请更新 data/xhs_cookie.txt 后重试",
        )
    return info


def fetch_notes_by_ids(
    note_ids: list[str],
    *,
    max_workers: int = 4,
    try_mobile_fallback: bool = True,
) -> list[NoteInfo | NoteFetchError]:
    """并行抓取多条；失败项返回 NoteFetchError 实例（与 NoteInfo 混排在结果列表中）。"""
    ids = [normalize_note_id(n) for n in note_ids]
    out_map: dict[str, NoteInfo | NoteFetchError] = {}

    def _one(nid: str) -> tuple[str, NoteInfo | NoteFetchError]:
        try:
            return nid, fetch_note_by_id(nid, try_mobile_fallback=try_mobile_fallback)
        except NoteFetchError as e:
            return nid, e

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 16))) as ex:
        futs = {ex.submit(_one, nid): nid for nid in ids}
        for fut in as_completed(futs):
            nid, item = fut.result()
            out_map[nid] = item

    return [out_map[nid] for nid in ids]
