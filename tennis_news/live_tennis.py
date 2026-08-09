#!/usr/bin/env python3
"""live-tennis.cn 首页新闻：抓取 + 解析（纯标准库，无第三方依赖）。

首页动态流位于 `cHomeWheelDesc` 卡片中：
    <div class="cHomeWheelDescText">恭喜 郭涵煜<br>生涯双打排名首次进入TOP10</div>
    <div class="cHomeWheelDescDot">... 2026/07/20 ... 温网</div>

本模块只负责「取 HTML」与「把 HTML 解析成标准新闻行」，不依赖 services，
因此可被 services.news_feed 反向导入而不产生循环依赖。
"""
from __future__ import annotations

import hashlib
import re
import ssl
import time
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HOME_URL = "https://www.live-tennis.cn/zh/home"
SOURCE_NAME = "Live Tennis CN"
SOURCE_DOMAIN = "live-tennis.cn"
SOURCE_TIER = 3

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# 首页轮播：每个 swiper-slide 自带 data-background 封面图 + 标题/日期。
# 例：data-background="…/trophies/1200x648_…_cropped.webp"
# 兜底：无 slide 包裹时仍按 Text+Dot 配对
_CARD_RE = re.compile(
    r'cHomeWheelDescText">(?P<title>.*?)</div>\s*'
    r'<div class="cHomeWheelDescDot">(?P<dot>.*?)</div>',
    re.S,
)
_TEXT_ONLY_RE = re.compile(r'cHomeWheelDescText">(.*?)</div>', re.S)
_DATE_RE = re.compile(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})")

# 生日提醒等非新闻卡片的过滤词 / 通用生日图
_SKIP_KEYWORDS = ("生日快乐",)
_SKIP_IMAGE_SUBSTR = ("happy_birthday", "/images/tips/loading")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _clean(raw: str) -> str:
    """去标签、还原实体、<br> 转空格、压缩空白。"""
    text = re.sub(r"<br\s*/?>", " ", raw or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    # 去掉站点 iconfont 私有区字形（U+E000–U+F8FF），避免混入标题/摘要
    text = re.sub(r"[\ue000-\uf8ff]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_home(url: str = HOME_URL, timeout: float = 20.0) -> dict[str, Any]:
    """抓取首页，返回包含 body/http/bytes 的结果字典（失败也不抛出）。"""
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "close",
            "Referer": "https://www.live-tennis.cn/",
        },
    )
    ctx = ssl.create_default_context()
    t0 = time.time()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(1_200_000)
            return {
                "ok": True,
                "url": url,
                "final_url": resp.geturl(),
                "http": int(getattr(resp, "status", 200) or 200),
                "ctype": (resp.headers.get("Content-Type") or "")[:80],
                "bytes": len(raw),
                "sec": round(time.time() - t0, 2),
                "body": raw.decode("utf-8", "ignore"),
                "error": "",
            }
    except HTTPError as exc:
        return _fail(url, int(exc.code), f"HTTP {exc.code}", t0)
    except URLError as exc:
        return _fail(url, 0, str(exc.reason), t0)
    except Exception as exc:  # noqa: BLE001 - 网络异常统一兜底
        return _fail(url, 0, f"{type(exc).__name__}: {exc}", t0)


def _fail(url: str, http: int, error: str, t0: float) -> dict[str, Any]:
    return {
        "ok": False,
        "url": url,
        "final_url": url,
        "http": http,
        "ctype": "",
        "bytes": 0,
        "sec": round(time.time() - t0, 2),
        "body": "",
        "error": error,
    }


def _published_iso(date_text: str) -> str:
    m = _DATE_RE.search(date_text or "")
    if not m:
        return _to_iso(_utc_now())
    y, mo, d = (int(x) for x in m.groups())
    try:
        return _to_iso(datetime(y, mo, d, 12, 0, 0, tzinfo=timezone.utc))
    except ValueError:
        return _to_iso(_utc_now())


def _infer_tags(title: str, venue: str) -> list[str]:
    blob = f"{title} {venue}"
    tags: list[str] = ["赛事"]
    if re.search(r"夺冠|锦标赛|决赛", blob):
        tags.append("冠军")
    if re.search(r"排名|TOP|上升|下降", blob, re.I):
        tags.append("排名")
    # 站点为中文综合站，男女混排，无法从姓名可靠区分 ATP/WTA，故不强打巡回赛标签。
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _normalize_image_url(raw: str) -> str:
    """清洗封面 URL；过滤生日图/加载占位图。"""
    url = (raw or "").strip()
    if not url.startswith("http"):
        return ""
    low = url.lower()
    if any(s in low for s in _SKIP_IMAGE_SUBSTR):
        return ""
    return url


def _extract_slide_cards(html: str) -> list[tuple[str, str, str]]:
    """从首页轮播抽出 (title_html, dot_html, image_url)。

    优先按 swiper-slide 切分（每张幻灯片自带 data-background）；
    失败则回退到仅 Text+Dot 配对（无图）。
    """
    parts = re.split(r'(?=<div class="swiper-slide\b)', html)
    out: list[tuple[str, str, str]] = []
    for part in parts:
        if "cHomeWheelDescText" not in part:
            continue
        img_m = re.search(r'data-background="([^"]+)"', part)
        image_url = _normalize_image_url(img_m.group(1) if img_m else "")
        tm = re.search(r'cHomeWheelDescText">(.*?)</div>', part, flags=re.S)
        if not tm:
            continue
        dm = re.search(r'cHomeWheelDescDot">(.*?)</div>', part, flags=re.S)
        out.append((tm.group(1), dm.group(1) if dm else "", image_url))
    if out:
        return out
    # 兜底：站点结构变化时至少抓到标题
    fallback = _CARD_RE.findall(html)
    if fallback:
        return [(t, d, "") for t, d in fallback]
    return [(t, "", "") for t in _TEXT_ONLY_RE.findall(html)]


def parse_home_items(
    html: str,
    cap: int = 80,
    *,
    source_name: str = SOURCE_NAME,
    source_domain: str = SOURCE_DOMAIN,
    source_tier: int = SOURCE_TIER,
) -> list[dict[str, Any]]:
    """把首页 HTML 解析为标准新闻行（与 services.news_feed 的行结构一致）。

    每行含唯一 `url`（用标题哈希做锚点），以适配 news_articles 的 UNIQUE(url)。
    封面优先取 swiper-slide 的 data-background（站点 trophies 图）。
    """
    rows: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    now_iso = _to_iso(_utc_now())

    for raw_title, raw_dot, image_url in _extract_slide_cards(html):
        title = _clean(raw_title)
        if not title or title in seen_titles:
            continue
        if any(kw in title for kw in _SKIP_KEYWORDS):
            continue

        dot = _clean(raw_dot)
        date_m = _DATE_RE.search(dot)
        date_str = date_m.group(0) if date_m else ""
        venue = dot
        if date_m:
            venue = _clean(dot[date_m.end() :])
        summary = " · ".join(x for x in (date_str, venue) if x) or title

        seen_titles.add(title)
        digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]
        rows.append(
            {
                "source": source_name,
                "source_domain": source_domain,
                "source_tier": int(source_tier),
                "title": title,
                "summary": summary,
                "url": f"{HOME_URL}#lt-{digest}",
                "image_url": image_url,
                "tags_csv": ",".join(_infer_tags(title, venue)),
                "published_at": _published_iso(date_str),
                "ingested_at": now_iso,
            }
        )
        if len(rows) >= cap:
            break
    return rows
