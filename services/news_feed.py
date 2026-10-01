from __future__ import annotations

import http.cookiejar
import json
import logging
import os
import re
import sqlite3
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from xml.etree import ElementTree as ET
import threading

from rec.tags import TAG_KEYWORDS, split_tags_csv, title_looks_like_tennis

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "news_feed.db"
_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class NewsSource:
    name: str
    url: str
    kind: str  # rss | html
    quality_tier: int  # 3=官方机构, 2=主流媒体, 1=聚合/其它
    parser: str | None = None  # html 子类型：tennis_com_list | thepaper_list；省略时按域名推断
    source_id: str = ""  # config 中的 id，用于打 ATP/WTA 等标签


def _news_sources_config_path() -> Path:
    raw = (os.environ.get("TENCLIP_NEWS_SOURCES_CONFIG") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _REPO_ROOT / "config" / "news_sources.json"


def _sources_from_json(path: Path) -> list[NewsSource]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[NewsSource] = []
    for i, item in enumerate(raw.get("sources", [])):
        if not item.get("enabled", True):
            continue
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        kind = str(item.get("kind", "rss")).strip().lower()
        if not name or not url:
            logger.warning("news_sources.json #%s 缺少 name/url，跳过", i)
            continue
        tier = int(item.get("quality_tier", 1))
        parser_raw = item.get("parser")
        parser = str(parser_raw).strip() if parser_raw else None
        out.append(
            NewsSource(
                name=name,
                url=url,
                kind=kind,
                quality_tier=tier,
                parser=parser or None,
                source_id=str(item.get("id") or "").strip(),
            )
        )
    if not out:
        raise ValueError("news_sources.json 中没有任何已启用的来源")
    return out


def _default_news_sources() -> list[NewsSource]:
    """配置文件缺失时的兜底：与默认开启的国内源一致。"""
    return [
        NewsSource(
            name="Live Tennis CN",
            url="https://www.live-tennis.cn/zh/home",
            kind="html",
            quality_tier=3,
            parser="live_tennis_list",
            source_id="live_tennis_cn_home",
        ),
        NewsSource(
            name="ThePaper Sports",
            url="https://m.thepaper.cn/list_25599",
            kind="html",
            quality_tier=2,
            parser="thepaper_list",
            source_id="thepaper_sports",
        ),
    ]


def get_news_sources() -> list[NewsSource]:
    path = _news_sources_config_path()
    if path.is_file():
        try:
            return _sources_from_json(path)
        except Exception as exc:
            logger.warning("读取 %s 失败，使用内置默认来源：%s", path, exc)
    return _default_news_sources()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: str | None) -> datetime:
    if not raw:
        return _utc_now()
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return _utc_now()


def _clean_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _infer_tags(title: str, summary: str, source: NewsSource | None = None) -> list[str]:
    hay = f" {title} {summary} ".lower()
    out: list[str] = []
    for tag, kws in TAG_KEYWORDS.items():
        if any(kw in hay for kw in kws):
            out.append(tag)
    if source is not None:
        sid = (source.source_id or "").lower()
        sname = (source.name or "").lower()
        if "atp" in sid or "atp" in sname:
            if "ATP" not in out:
                out.append("ATP")
            if "赛事" not in out:
                out.append("赛事")
        if "wta" in sid or "wta" in sname:
            if "WTA" not in out:
                out.append("WTA")
            if "赛事" not in out:
                out.append("赛事")
        if "tennis_com" in sid or "espn_tennis" in sid or "bbc_tennis" in sid:
            if "赛事" not in out and ("ATP" in out or "WTA" in out):
                out.append("赛事")
    # 去重保序
    seen: set[str] = set()
    ordered: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("环境变量 %s 无效，使用默认 %.2f", name, default)
        return default


def news_http_timeout_sec() -> float:
    """单次 HTTP 读超时上限（秒），过小易失败，过大易拖住线程。"""
    return max(3.0, min(_env_float("TENCLIP_NEWS_HTTP_TIMEOUT_SEC", 12.0), 45.0))


def news_source_total_timeout_sec() -> float:
    """单个来源「抓取 + 解析」总预算（秒）；超时则放弃该来源，继续下一个。"""
    return max(8.0, min(_env_float("TENCLIP_NEWS_SOURCE_TIMEOUT_SEC", 28.0), 120.0))


def init_news_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_domain TEXT,
                source_tier INTEGER NOT NULL DEFAULT 1,
                title TEXT NOT NULL,
                summary TEXT,
                url TEXT NOT NULL UNIQUE,
                image_url TEXT,
                tags_csv TEXT,
                published_at TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                popularity REAL NOT NULL DEFAULT 0
            )
            """
        )
        cols = conn.execute("PRAGMA table_info(news_articles)").fetchall()
        col_names = {c[1] for c in cols}
        if "source_tier" not in col_names:
            conn.execute("ALTER TABLE news_articles ADD COLUMN source_tier INTEGER NOT NULL DEFAULT 1")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                article_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_user_profile (
                user_id TEXT PRIMARY KEY,
                tags_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_feedback_user ON news_feedback(user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_ingest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                status TEXT NOT NULL,
                limit_per_source INTEGER NOT NULL,
                inserted_or_updated INTEGER NOT NULL DEFAULT 0,
                sources_ok TEXT,
                sources_failed TEXT,
                detail_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_source_circuit (
                source_key TEXT PRIMARY KEY,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                last_ok_at TEXT,
                last_fail_at TEXT,
                last_error TEXT,
                open_until TEXT
            )
            """
        )
        conn.commit()


def _request_headers(url: str) -> dict[str, str]:
    """尽量模拟浏览器，降低 ATP/ESPN 等站点的 403 概率。"""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    if "atptour.com" in host:
        referer = "https://www.atptour.com/en/media/rss-feed"
    if "espn.com" in host:
        referer = "https://www.espn.com/tennis/"
    if "bbc.co.uk" in host or "bbci.co.uk" in host:
        referer = "https://www.bbc.com/sport/tennis"
    if "cnn.com" in host or "turner.com" in host:
        referer = "https://edition.cnn.com/sport"
    if "tennis.com" in host:
        referer = "https://www.tennis.com/news/all-news/"
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Referer": referer,
        "Connection": "close",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }


def _fetch_xml(url: str, timeout_sec: float | None = None) -> str:
    if timeout_sec is None:
        timeout_sec = news_http_timeout_sec()
    headers = _request_headers(url)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if "news.google.com" in host:
        timeout_sec = min(timeout_sec, 11.0)
    try:
        # ATP 常见策略：先访问主站拿 Cookie，再拉 RSS，可降低 403。
        if "atptour.com" in host:
            jar = http.cookiejar.CookieJar()
            opener = build_opener(HTTPCookieProcessor(jar))
            warmup_urls = (
                "https://www.atptour.com/",
                "https://www.atptour.com/en/",
            )
            per_warm = min(7.0, max(3.0, timeout_sec * 0.45))
            for wu in warmup_urls:
                try:
                    opener.open(Request(wu, headers=_request_headers(wu)), timeout=per_warm)
                except Exception:
                    continue
            with opener.open(Request(url, headers=headers), timeout=timeout_sec) as resp:
                return resp.read().decode("utf-8", errors="ignore")

        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout_sec) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except HTTPError as exc:
        logger.warning("HTTP %s for %s", exc.code, url)
        raise
    except URLError as exc:
        logger.warning("URL error for %s: %s", url, exc)
        raise


def _pick(el: ET.Element, *paths: str) -> str:
    for p in paths:
        node = el.find(p)
        if node is not None and node.text:
            return node.text.strip()
    return ""


def _item_link(it: ET.Element) -> str:
    link = _pick(it, "link")
    if link:
        return link.strip()
    # Google News 等偶发把链接放在 guid
    guid_el = it.find("guid")
    if guid_el is not None and guid_el.text and guid_el.text.strip().startswith("http"):
        return guid_el.text.strip()
    # Atom 风格 <link href="..."/>
    for child in list(it):
        tag = child.tag.split("}")[-1]
        if tag == "link" and child.get("href"):
            return (child.get("href") or "").strip()
    return ""


def _parse_rss_items(source: NewsSource, xml_text: str, cap: int) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("RSS XML 解析失败 %s: %s", source.name, exc)
        return []
    items = root.findall(".//item")
    out: list[dict[str, Any]] = []
    for it in items[:cap]:
        title = _pick(it, "title")
        link = _item_link(it)
        if not title or not link:
            continue
        summary = _clean_html(_pick(it, "description", "content:encoded"))
        pub_raw = _pick(it, "pubDate", "published")
        pub_dt = _parse_dt(pub_raw)
        image_url = ""
        enclosure = it.find("enclosure")
        if enclosure is not None:
            image_url = (enclosure.attrib.get("url") or "").strip()
        if not image_url:
            # CNN / 部分站点使用 Yahoo media RSS（media:thumbnail / media:content，可能在 group 内）
            for child in it.iter():
                tag = child.tag.split("}")[-1]
                if tag in ("thumbnail", "content") and (child.get("url") or "").strip():
                    image_url = (child.get("url") or "").strip()
                    break
        if not image_url:
            image_url = ""
        tags = _infer_tags(title, summary, source)
        domain = (urlparse(link).hostname or "").replace("www.", "")
        out.append(
            {
                "source": source.name,
                "source_domain": domain,
                "source_tier": int(source.quality_tier),
                "title": title,
                "summary": summary,
                "url": link.strip(),
                "image_url": image_url,
                "tags_csv": ",".join(tags),
                "published_at": _to_iso(pub_dt),
                "ingested_at": _to_iso(_utc_now()),
            }
        )
    return out


_THEPAPER_PORTAL = "https://api.thepaper.cn/contentapi/nodeCont/getByNodeIdPortal"
_THEPAPER_NODE_ID = "25599"
_THEPAPER_CHANNEL_PIC = "depository/image/8/964/843"


def _thepaper_cover(item: dict[str, Any]) -> str:
    """列表项封面。跳过栏目头图，避免整页共用同一张运动家 logo。"""
    for key in ("smallPic", "pic", "sharePic"):
        url = str(item.get(key) or "").strip().replace("\\/", "/")
        if url.startswith("http") and _THEPAPER_CHANNEL_PIC not in url:
            return url
    return ""


def _thepaper_published(item: dict[str, Any], now_iso: str) -> str:
    raw = str(item.get("publishTime") or "").strip()
    if not raw:
        return now_iso
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=8)))
        return dt.isoformat()
    except Exception:
        return now_iso


def _thepaper_rows_from_items(
    source: NewsSource, items: list[dict[str, Any]], cap: int
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_url: set[str] = set()
    now_iso = _to_iso(_utc_now())
    for item in items:
        cid = str(item.get("contId") or "").strip()
        title = re.sub(r"\s+", " ", str(item.get("name") or "").strip())
        if not cid or len(title) < 4 or title.startswith("澎湃新闻 · 文章"):
            continue
        full = f"https://www.thepaper.cn/newsDetail_forward_{cid}"
        if full in seen_url:
            continue
        seen_url.add(full)
        tags = _infer_tags(title, "", source)
        if title_looks_like_tennis(title) and "网球" not in tags:
            tags = ["网球", *tags]
        out.append(
            {
                "source": source.name,
                "source_domain": "thepaper.cn",
                "source_tier": int(source.quality_tier),
                "title": title,
                "summary": "",
                "url": full,
                "image_url": _thepaper_cover(item),
                "tags_csv": ",".join(tags),
                "published_at": _thepaper_published(item, now_iso),
                "ingested_at": now_iso,
            }
        )
    out.sort(key=lambda row: (0 if title_looks_like_tennis(row["title"]) else 1))
    return out[: max(1, int(cap))]


def _thepaper_next_data_list(html: str) -> list[dict[str, Any]]:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html or "",
        flags=re.S,
    )
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    page = ((data.get("props") or {}).get("pageProps") or {}).get("data") or {}
    items = page.get("list") or []
    return [x for x in items if isinstance(x, dict)]


def _parse_thepaper_html(source: NewsSource, html: str, cap: int) -> list[dict[str, Any]]:
    """澎湃运动家列表：入库整页体育，网球标题排在前面再截断 cap。"""
    items = _thepaper_next_data_list(html)
    if items:
        return _thepaper_rows_from_items(source, items, cap)
    id_iter = re.finditer(r"newsDetail_forward_(\d{6,})", html)
    ids_ordered: list[str] = []
    seen_ids: set[str] = set()
    for m in id_iter:
        cid = m.group(1)
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        ids_ordered.append(cid)

    def _title_near(cont_id: str) -> str:
        needle = f"newsDetail_forward_{cont_id}"
        pos = html.find(needle)
        if pos < 0:
            return ""
        lo = max(0, pos - 3500)
        hi = min(len(html), pos + 3500)
        chunk = html[lo:hi]
        for pat in (
            r'"title"\s*:\s*"([^"]{4,220})"',
            r'"name"\s*:\s*"([^"]{4,220})"',
            r'"shareTitle"\s*:\s*"([^"]{4,220})"',
            r'"desc"\s*:\s*"([^"]{4,220})"',
        ):
            tm = re.search(pat, chunk)
            if tm:
                t = tm.group(1).strip().replace("\\/", "/")
                if "\\u" in t:
                    try:
                        t = t.encode("utf-8", "ignore").decode("unicode_escape", "ignore")
                    except Exception:
                        pass
                if len(t) >= 4:
                    return re.sub(r"\s+", " ", t).strip()
        return ""

    out: list[dict[str, Any]] = []
    seen_url: set[str] = set()
    now_iso = _to_iso(_utc_now())
    for cid in ids_ordered:
        full = f"https://www.thepaper.cn/newsDetail_forward_{cid}"
        if full in seen_url:
            continue
        seen_url.add(full)
        title = _title_near(cid)
        if not title or title.startswith("澎湃新闻 · 文章"):
            continue
        tags = _infer_tags(title, "", source)
        if title_looks_like_tennis(title) and "网球" not in tags:
            tags = ["网球", *tags]
        out.append(
            {
                "source": source.name,
                "source_domain": "thepaper.cn",
                "source_tier": int(source.quality_tier),
                "title": title,
                "summary": "",
                "url": full,
                "image_url": "",
                "tags_csv": ",".join(tags),
                "published_at": now_iso,
                "ingested_at": now_iso,
            }
        )
    out.sort(key=lambda row: (0 if title_looks_like_tennis(row["title"]) else 1))
    return out[: max(1, int(cap))]


def _parse_tennis_com_all_news_html(source: NewsSource, html: str, cap: int) -> list[dict[str, Any]]:
    """解析 Tennis.com 列表页：抽取 /news/articles/ 链接与可见标题。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    paired = re.findall(
        r'href="(https://www\.tennis\.com/news/articles/[^"#?]+)"[^>]{0,160}>([^<]{6,240})</a>',
        html,
        flags=re.I,
    )
    for url, title in paired:
        u = url.strip()
        t = re.sub(r"\s+", " ", (title or "").replace("Read More", "").strip())
        if not u or u in seen:
            continue
        seen.add(u)
        if len(t) < 6:
            slug = u.rstrip("/").split("/")[-1]
            t = " ".join(slug.split("-")).strip().title()
        tags = _infer_tags(t, "", source)
        out.append(
            {
                "source": source.name,
                "source_domain": "tennis.com",
                "source_tier": int(source.quality_tier),
                "title": t,
                "summary": "",
                "url": u,
                "image_url": "",
                "tags_csv": ",".join(tags),
                "published_at": _to_iso(_utc_now()),
                "ingested_at": _to_iso(_utc_now()),
            }
        )
        if len(out) >= cap:
            return out

    hrefs = re.findall(r'href="(https://www\.tennis\.com/news/articles/[^"#?]+)"', html, flags=re.I)
    for u in hrefs:
        u = u.strip()
        if not u or u in seen:
            continue
        seen.add(u)
        slug = u.rstrip("/").split("/")[-1]
        t = " ".join(slug.split("-")).strip().title()
        tags = _infer_tags(t, "", source)
        out.append(
            {
                "source": source.name,
                "source_domain": "tennis.com",
                "source_tier": int(source.quality_tier),
                "title": t,
                "summary": "",
                "url": u,
                "image_url": "",
                "tags_csv": ",".join(tags),
                "published_at": _to_iso(_utc_now()),
                "ingested_at": _to_iso(_utc_now()),
            }
        )
        if len(out) >= cap:
            break
    return out


def _ingest_one_source_rows(source: NewsSource, limit_per_source: int) -> list[dict[str, Any]]:
    """在独立线程中执行网络与解析，供外层 `result(timeout=...)` 做硬超时。"""
    raw_text = _fetch_xml(source.url)
    if source.kind == "rss":
        return _parse_rss_items(source, raw_text, cap=limit_per_source)
    if source.kind == "html":
        host = (urlparse(source.url).hostname or "").lower()
        p = (source.parser or "").strip().lower()
        if p == "tennis_com_list" or (not p and "tennis.com" in host):
            return _parse_tennis_com_all_news_html(source, raw_text, cap=limit_per_source)
        if p == "thepaper_list" or (not p and "thepaper.cn" in host):
            return _parse_thepaper_html(source, raw_text, cap=limit_per_source)
        if p == "live_tennis_list" or (not p and "live-tennis.cn" in host):
            # 复用 tennis_news 包的解析逻辑（纯标准库，不反向依赖本模块）
            from tennis_news.live_tennis import parse_home_items

            return parse_home_items(
                raw_text,
                cap=limit_per_source,
                source_name=source.name,
                source_tier=int(source.quality_tier),
            )
        logger.warning("html 来源未识别 parser/域名，跳过：%s (%s)", source.name, source.url)
        return []
    return []


def _run_source_with_timeout(
    source: NewsSource, limit_per_source: int, timeout_sec: float
) -> list[dict[str, Any]]:
    """在 daemon 线程中抓取单源；超时抛 FuturesTimeoutError，且不阻塞进程退出。"""
    box: dict[str, Any] = {"rows": None, "exc": None}

    def _target() -> None:
        try:
            box["rows"] = _ingest_one_source_rows(source, limit_per_source)
        except Exception as exc:  # noqa: BLE001 - 交给外层统一记 failed
            box["exc"] = exc

    t = threading.Thread(target=_target, name=f"news-ingest:{source.name[:24]}", daemon=True)
    t.start()
    t.join(timeout=timeout_sec)
    if t.is_alive():
        raise FuturesTimeoutError()
    if box["exc"] is not None:
        raise box["exc"]
    return list(box["rows"] or [])


def _circuit_key(source: NewsSource) -> str:
    return (source.source_id or source.name or source.url).strip()


def _circuit_is_open(conn: sqlite3.Connection, key: str, now_iso: str) -> bool:
    row = conn.execute(
        "SELECT open_until FROM news_source_circuit WHERE source_key=?",
        (key,),
    ).fetchone()
    if not row or not row[0]:
        return False
    return str(row[0]) > now_iso


def _circuit_record_ok(conn: sqlite3.Connection, key: str, now_iso: str) -> None:
    conn.execute(
        """
        INSERT INTO news_source_circuit(
            source_key, consecutive_failures, last_ok_at, last_fail_at, last_error, open_until
        ) VALUES (?, 0, ?, NULL, NULL, NULL)
        ON CONFLICT(source_key) DO UPDATE SET
            consecutive_failures=0,
            last_ok_at=excluded.last_ok_at,
            last_error=NULL,
            open_until=NULL
        """,
        (key, now_iso),
    )


def _circuit_record_fail(
    conn: sqlite3.Connection,
    key: str,
    now_iso: str,
    err: str,
    *,
    fail_open: int = 5,
    cooldown_hours: int = 6,
) -> None:
    row = conn.execute(
        "SELECT consecutive_failures FROM news_source_circuit WHERE source_key=?",
        (key,),
    ).fetchone()
    n = int(row[0] if row else 0) + 1
    open_until = _to_iso(_utc_now() + timedelta(hours=cooldown_hours)) if n >= fail_open else None
    conn.execute(
        """
        INSERT INTO news_source_circuit(
            source_key, consecutive_failures, last_ok_at, last_fail_at, last_error, open_until
        ) VALUES (?, ?, NULL, ?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
            consecutive_failures=excluded.consecutive_failures,
            last_fail_at=excluded.last_fail_at,
            last_error=excluded.last_error,
            open_until=excluded.open_until
        """,
        (key, n, now_iso, (err or "")[:500], open_until),
    )


def _extract_og_image(html: str) -> str:
    m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html or "",
        flags=re.I,
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        html or "",
        flags=re.I,
    )
    return (m.group(1).strip() if m else "")


def _fetch_html(url: str, timeout_sec: float = 6.0) -> str:
    headers = _request_headers(url)
    headers["Accept"] = "text/html,application/xhtml+xml,*/*;q=0.8"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=max(2.0, timeout_sec)) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _fill_missing_og_images(rows: list[dict[str, Any]], budget: int) -> int:
    used = 0
    for row in rows:
        if used >= budget:
            break
        if (row.get("image_url") or "").strip():
            continue
        url = (row.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        try:
            html = _fetch_html(url, timeout_sec=6.0)
            img = _extract_og_image(html)
            if img:
                row["image_url"] = img
                used += 1
        except Exception:
            continue
    return used


def _thepaper_missing_covers(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT url FROM news_articles
        WHERE source_domain='thepaper.cn'
          AND (image_url IS NULL OR TRIM(image_url)='')
        """
    ).fetchall()
    missing: dict[str, str] = {}
    for (url,) in rows:
        m = re.search(r"newsDetail_forward_(\d+)", url or "")
        if m:
            missing[m.group(1)] = url
    return missing


def _fetch_thepaper_portal_page(start_time: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "nodeId": _THEPAPER_NODE_ID,
        "excludeContIds": [],
        "pageSize": 20,
    }
    if start_time:
        payload["startTime"] = int(start_time)
    req = Request(
        _THEPAPER_PORTAL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": _request_headers(_THEPAPER_PORTAL)["User-Agent"],
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": "https://m.thepaper.cn/list_25599",
        },
    )
    with urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    return data if isinstance(data, dict) else {}


def _thepaper_detail_cover(cont_id: str) -> str:
    url = f"https://www.thepaper.cn/newsDetail_forward_{cont_id}"
    html = _fetch_html(url, timeout_sec=8.0)
    items = _thepaper_next_data_list(html)
    if items:
        cover = _thepaper_cover(items[0])
        if cover:
            return cover
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        flags=re.S,
    )
    if not m:
        return ""
    try:
        data = json.loads(m.group(1))
    except Exception:
        return ""
    detail = ((data.get("props") or {}).get("pageProps") or {}).get("detailData") or {}
    content = detail.get("contentDetail") if isinstance(detail, dict) else None
    if isinstance(content, dict):
        return _thepaper_cover(content)
    return ""


def _backfill_thepaper_detail_covers(
    conn: sqlite3.Connection, missing: dict[str, str], limit: int = 12
) -> int:
    """频道翻页没覆盖到的旧稿，逐篇打开详情补封面。占位标题不补。"""
    if not missing or limit <= 0:
        return 0
    urls = list(missing.items())
    filled = 0
    for cid, url in urls:
        if filled >= limit:
            break
        title_row = conn.execute(
            "SELECT title FROM news_articles WHERE url=?",
            (url,),
        ).fetchone()
        title = (title_row[0] if title_row else "") or ""
        if title.startswith("澎湃新闻 · 文章"):
            continue
        try:
            img = _thepaper_detail_cover(cid)
        except Exception as exc:
            logger.warning("thepaper detail cover failed %s: %s", cid, exc)
            continue
        if not img:
            continue
        conn.execute(
            """
            UPDATE news_articles SET image_url=?
            WHERE url=? AND (image_url IS NULL OR TRIM(image_url)='')
            """,
            (img, url),
        )
        missing.pop(cid, None)
        filled += 1
        time.sleep(0.2)
    return filled


def _thepaper_detail_fields(cont_id: str) -> dict[str, str]:
    url = f"https://www.thepaper.cn/newsDetail_forward_{cont_id}"
    html = _fetch_html(url, timeout_sec=8.0)
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html or "",
        flags=re.S,
    )
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except Exception:
        return {}
    detail = ((data.get("props") or {}).get("pageProps") or {}).get("detailData") or {}
    content = detail.get("contentDetail") if isinstance(detail, dict) else None
    if not isinstance(content, dict):
        return {}
    title = re.sub(r"\s+", " ", str(content.get("name") or "").strip())
    return {"title": title, "image_url": _thepaper_cover(content)}


def _repair_thepaper_details(conn: sqlite3.Connection, limit: int = 400) -> int:
    """逐篇打开详情，把库里的标题和封面改成这篇稿自己的 name 和 pic。"""
    rows = conn.execute(
        """
        SELECT url, title, image_url FROM news_articles
        WHERE source_domain='thepaper.cn'
        ORDER BY id DESC
        """
    ).fetchall()
    fixed = 0
    fails = 0
    checked = 0
    for url, old_title, old_img in rows:
        if checked >= limit:
            break
        m = re.search(r"newsDetail_forward_(\d+)", url or "")
        if not m:
            continue
        checked += 1
        try:
            fields = _thepaper_detail_fields(m.group(1))
        except Exception as exc:
            fails += 1
            logger.warning("thepaper detail repair failed %s: %s", url, exc)
            if fails >= 8:
                break
            time.sleep(0.4)
            continue
        fails = 0
        title = fields.get("title") or ""
        img = fields.get("image_url") or ""
        if len(title) < 4:
            time.sleep(0.12)
            continue
        old_title = old_title or ""
        old_img = old_img or ""
        if old_title == title and (not img or old_img == img):
            time.sleep(0.05)
            continue
        tags = _infer_tags(title, "", None)
        if title_looks_like_tennis(title) and "网球" not in tags:
            tags = ["网球", *tags]
        conn.execute(
            """
            UPDATE news_articles
            SET title=?,
                image_url=CASE WHEN ? <> '' THEN ? ELSE image_url END,
                tags_csv=?
            WHERE url=?
            """,
            (title, img, img, ",".join(tags), url),
        )
        fixed += 1
        if fixed % 20 == 0:
            conn.commit()
        time.sleep(0.12)
    if fixed:
        logger.info("thepaper detail pairings repaired: %s", fixed)
    return fixed


def _repair_thepaper_pairings(conn: sqlite3.Connection, max_pages: int = 30) -> int:
    """用运动家列表里同一条的 name+pic 纠正已入库稿。

    旧解析在链接附近乱抓 title，封面后来又按 contId 补上，会出现标题和图片不是同一篇。
    """
    fixed = 0
    start: int | None = None
    seen_cursors: set[int] = set()
    empty_pages = 0
    for _ in range(max(1, int(max_pages))):
        try:
            data = _fetch_thepaper_portal_page(start)
        except Exception as exc:
            logger.warning("thepaper title repair failed: %s", exc)
            break
        page = data.get("data") or {}
        items = page.get("list") or []
        if not items:
            break
        page_hits = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("contId") or "").strip()
            title = re.sub(r"\s+", " ", str(item.get("name") or "").strip())
            if not cid or len(title) < 4 or title.startswith("澎湃新闻 · 文章"):
                continue
            url = f"https://www.thepaper.cn/newsDetail_forward_{cid}"
            row = conn.execute(
                "SELECT title, image_url FROM news_articles WHERE url=?",
                (url,),
            ).fetchone()
            if not row:
                continue
            page_hits += 1
            img = _thepaper_cover(item)
            old_title = row[0] or ""
            old_img = row[1] or ""
            if old_title == title and (not img or old_img == img):
                continue
            tags = _infer_tags(title, "", None)
            if title_looks_like_tennis(title) and "网球" not in tags:
                tags = ["网球", *tags]
            conn.execute(
                """
                UPDATE news_articles
                SET title=?,
                    image_url=CASE WHEN ? <> '' THEN ? ELSE image_url END,
                    tags_csv=?
                WHERE url=?
                """,
                (title, img, img, ",".join(tags), url),
            )
            fixed += 1
        if page_hits == 0:
            empty_pages += 1
            if empty_pages >= 2:
                break
        else:
            empty_pages = 0
        if not page.get("hasNext"):
            break
        try:
            nxt_i = int(page.get("startTime"))
        except (TypeError, ValueError):
            break
        if nxt_i in seen_cursors:
            break
        seen_cursors.add(nxt_i)
        start = nxt_i
        time.sleep(0.25)
    if fixed:
        logger.info("thepaper title/image pairings repaired: %s", fixed)
    return fixed


def _backfill_thepaper_images(conn: sqlite3.Connection, max_pages: int = 40) -> int:
    """按运动家频道往前翻页，给已入库但没封面的澎湃稿补图。补完即停。"""
    missing = _thepaper_missing_covers(conn)
    if not missing:
        return 0
    filled = 0
    start: int | None = None
    seen_cursors: set[int] = set()
    for _ in range(max(1, int(max_pages))):
        if not missing:
            break
        try:
            data = _fetch_thepaper_portal_page(start)
        except Exception as exc:
            logger.warning("thepaper cover backfill failed: %s", exc)
            break
        page = data.get("data") or {}
        items = page.get("list") or []
        if not items:
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("contId") or "")
            url = missing.get(cid)
            img = _thepaper_cover(item)
            if not url or not img:
                continue
            conn.execute(
                """
                UPDATE news_articles SET image_url=?
                WHERE url=? AND (image_url IS NULL OR TRIM(image_url)='')
                """,
                (img, url),
            )
            missing.pop(cid, None)
            filled += 1
        if not page.get("hasNext"):
            break
        nxt = page.get("startTime")
        try:
            nxt_i = int(nxt)
        except (TypeError, ValueError):
            break
        if nxt_i in seen_cursors:
            break
        seen_cursors.add(nxt_i)
        start = nxt_i
        time.sleep(0.25)
    filled += _backfill_thepaper_detail_covers(conn, missing, limit=12)
    if filled:
        logger.info("thepaper covers backfilled: %s, still missing %s", filled, len(missing))
    return filled


def _upsert_article(conn: sqlite3.Connection, row: dict[str, Any]) -> str:
    """写入一篇。返回 inserted | updated | unchanged。未变则不刷新 ingested_at。"""
    url = row["url"]
    existing = conn.execute(
        "SELECT title, summary, image_url FROM news_articles WHERE url=?",
        (url,),
    ).fetchone()
    title = row["title"]
    summary = row.get("summary") or ""
    image = row.get("image_url") or ""
    now_iso = row.get("ingested_at") or _to_iso(_utc_now())
    if existing is None:
        conn.execute(
            """
            INSERT INTO news_articles (
                source, source_domain, source_tier, title, summary, url, image_url,
                tags_csv, published_at, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["source"],
                row["source_domain"],
                row["source_tier"],
                title,
                summary,
                url,
                image,
                row.get("tags_csv") or "",
                row["published_at"],
                now_iso,
            ),
        )
        return "inserted"
    old_title, old_summary, old_image = existing
    if (
        (old_title or "") == title
        and (old_summary or "") == summary
        and (old_image or "") == image
    ):
        return "unchanged"
    conn.execute(
        """
        UPDATE news_articles SET
            source=?, source_domain=?, source_tier=?, title=?, summary=?,
            image_url=?, tags_csv=?, ingested_at=?
        WHERE url=?
        """,
        (
            row["source"],
            row["source_domain"],
            row["source_tier"],
            title,
            summary,
            image,
            row.get("tags_csv") or "",
            now_iso,
            url,
        ),
    )
    return "updated"


def ingest_news(limit_per_source: int = 20) -> dict[str, Any]:
    init_news_db()
    started = _to_iso(_utc_now())
    inserted = 0
    updated = 0
    unchanged = 0
    og_filled = 0
    og_budget = 5
    touched_sources: list[str] = []
    failed_sources: list[dict[str, str]] = []
    skipped_circuit: list[str] = []
    per_source_deadline = news_source_total_timeout_sec()
    http_cap = news_http_timeout_sec()
    with sqlite3.connect(DB_PATH) as conn:
        for source in get_news_sources():
            key = _circuit_key(source)
            if _circuit_is_open(conn, key, started):
                logger.info("ingest skip circuit-open: %s", source.name)
                skipped_circuit.append(source.name)
                continue
            rows: list[dict[str, Any]] = []
            try:
                rows = _run_source_with_timeout(source, limit_per_source, per_source_deadline)
            except FuturesTimeoutError:
                msg = f"source timeout (>{per_source_deadline:.0f}s)"
                logger.warning("ingest source timeout: %s", source.name)
                failed_sources.append({"source": source.name, "error": msg})
                _circuit_record_fail(conn, key, started, msg)
                continue
            except Exception as exc:
                logger.warning("ingest source failed: %s %s", source.name, exc)
                failed_sources.append({"source": source.name, "error": str(exc)})
                _circuit_record_fail(conn, key, started, str(exc))
                continue
            if not rows:
                msg = "no rows parsed"
                failed_sources.append({"source": source.name, "error": msg})
                _circuit_record_fail(conn, key, started, msg)
                continue
            og_filled += _fill_missing_og_images(rows, og_budget - og_filled)
            touched_sources.append(source.name)
            _circuit_record_ok(conn, key, started)
            for row in rows:
                kind = _upsert_article(conn, row)
                if kind == "inserted":
                    inserted += 1
                elif kind == "updated":
                    updated += 1
                else:
                    unchanged += 1
        images_backfilled = _backfill_thepaper_images(conn)
        titles_repaired = _repair_thepaper_pairings(conn)
        conn.commit()
    try:
        from rec.catalog import sync_news_from_db

        sync_news_from_db()
    except Exception:
        logger.exception("sync rec catalog after ingest_news failed")
    finished = _to_iso(_utc_now())
    result = {
        "inserted_or_updated": inserted + updated,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "og_images_filled": og_filled,
        "thepaper_images_backfilled": images_backfilled,
        "thepaper_titles_repaired": titles_repaired,
        "sources": touched_sources,
        "failed": failed_sources,
        "skipped_circuit": skipped_circuit,
        "http_timeout_sec": http_cap,
        "source_timeout_sec": per_source_deadline,
        "started_at": started,
        "finished_at": finished,
    }
    status = "ok" if touched_sources else "failed"
    if touched_sources and failed_sources:
        status = "partial"
    _record_ingest_run(
        started_at=started,
        finished_at=finished,
        status=status,
        limit_per_source=limit_per_source,
        result=result,
    )
    return result


def _record_ingest_run(
    *,
    started_at: str,
    finished_at: str,
    status: str,
    limit_per_source: int,
    result: dict[str, Any],
) -> None:
    init_news_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO news_ingest_runs(
                started_at, finished_at, status, limit_per_source,
                inserted_or_updated, sources_ok, sources_failed, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at,
                finished_at,
                status,
                int(limit_per_source),
                int(result.get("inserted_or_updated") or 0),
                json.dumps(result.get("sources") or [], ensure_ascii=False),
                json.dumps(result.get("failed") or [], ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
            ),
        )
        conn.commit()


def list_ingest_runs(limit: int = 20) -> list[dict[str, Any]]:
    init_news_db()
    limit = max(1, min(int(limit), 100))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, started_at, finished_at, status, limit_per_source,
                   inserted_or_updated, sources_ok, sources_failed
            FROM news_ingest_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        try:
            item["sources_ok"] = json.loads(r["sources_ok"] or "[]")
        except Exception:
            item["sources_ok"] = []
        try:
            item["sources_failed"] = json.loads(r["sources_failed"] or "[]")
        except Exception:
            item["sources_failed"] = []
        out.append(item)
    return out


def news_ingest_health(*, stale_after_hours: float = 6.0) -> dict[str, Any]:
    """供 /api/mobile/health：最近一次成功抓取是否过期。"""
    init_news_db()
    with sqlite3.connect(DB_PATH) as conn:
        n = int(conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0])
        last = conn.execute(
            "SELECT finished_at, status FROM news_ingest_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        last_ok = conn.execute(
            """
            SELECT finished_at FROM news_ingest_runs
            WHERE status IN ('ok', 'partial')
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    last_at = last[0] if last else None
    last_status = last[1] if last else None
    last_ok_at = last_ok[0] if last_ok else None
    hours: float | None = None
    stale = True
    if last_ok_at:
        try:
            dt = datetime.fromisoformat(str(last_ok_at).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours = (_utc_now() - dt.astimezone(timezone.utc)).total_seconds() / 3600.0
            stale = hours > float(stale_after_hours)
        except Exception:
            stale = True
    return {
        "news_articles": n,
        "news_last_ingest_at": last_at,
        "news_last_ingest_ok_at": last_ok_at,
        "news_last_ingest_status": last_status,
        "news_hours_since_ok": (round(hours, 2) if hours is not None else None),
        "news_ingest_stale": stale,
    }


def _category_distribution_from_db(conn: sqlite3.Connection, total: int) -> tuple[list[dict[str, Any]], bool]:
    """优先用 tags 真实统计 ATP/WTA/赛事/教学；样本不足时回退 mock 比例。"""
    rows = conn.execute(
        "SELECT tags_csv FROM news_articles WHERE tags_csv IS NOT NULL AND TRIM(tags_csv) <> ''"
    ).fetchall()
    freq = {"ATP": 0, "WTA": 0, "赛事": 0, "教学": 0, "其它": 0}
    tagged = 0
    for (csv_tags,) in rows:
        tags = set(split_tags_csv(csv_tags))
        if not tags:
            continue
        tagged += 1
        hit = False
        for key in ("ATP", "WTA", "赛事", "教学"):
            if key in tags:
                freq[key] += 1
                hit = True
        if not hit:
            freq["其它"] += 1
    if tagged < max(5, int(total * 0.15)):
        return _mock_category_distribution(total), True
    out = [
        {"name": k, "count": freq[k], "pct": round(100.0 * freq[k] / max(1, tagged), 1)}
        for k in ("ATP", "WTA", "赛事", "教学", "其它")
        if freq[k] > 0 or k in ("ATP", "WTA", "赛事")
    ]
    return out, False


def _mock_category_distribution(total: int) -> list[dict[str, Any]]:
    """类目尚未正式标注时的示意比例。"""
    if total <= 0:
        return [
            {"name": "ATP", "count": 0, "pct": 0.0},
            {"name": "WTA", "count": 0, "pct": 0.0},
            {"name": "赛事", "count": 0, "pct": 0.0},
            {"name": "教学", "count": 0, "pct": 0.0},
        ]
    weights = [("ATP", 0.32), ("WTA", 0.28), ("赛事", 0.25), ("教学", 0.15)]
    counts: list[int] = []
    used = 0
    for i, (_, w) in enumerate(weights):
        if i == len(weights) - 1:
            c = max(0, total - used)
        else:
            c = int(round(total * w))
            used += c
        counts.append(c)
    diff = total - sum(counts)
    counts[0] = max(0, counts[0] + diff)
    return [
        {"name": name, "count": counts[i], "pct": round(100.0 * counts[i] / total, 1)}
        for i, (name, _) in enumerate(weights)
    ]


def get_news_admin_overview() -> dict[str, Any]:
    init_news_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total = int(conn.execute("SELECT COUNT(*) AS c FROM news_articles").fetchone()["c"])
        with_image = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM news_articles WHERE image_url IS NOT NULL AND TRIM(image_url) <> ''"
            ).fetchone()["c"]
        )
        feedback_n = int(conn.execute("SELECT COUNT(*) AS c FROM news_feedback").fetchone()["c"])
        profile_n = int(conn.execute("SELECT COUNT(*) AS c FROM news_user_profile").fetchone()["c"])
        by_source_rows = conn.execute(
            """
            SELECT source, COUNT(*) AS c
            FROM news_articles
            GROUP BY source
            ORDER BY c DESC
            LIMIT 30
            """
        ).fetchall()
        latest = conn.execute(
            """
            SELECT id, source, title, url, published_at, ingested_at,
                   CASE WHEN image_url IS NOT NULL AND TRIM(image_url) <> '' THEN 1 ELSE 0 END AS has_image
            FROM news_articles
            ORDER BY datetime(ingested_at) DESC
            LIMIT 15
            """
        ).fetchall()
        latest_pub = conn.execute(
            "SELECT published_at FROM news_articles ORDER BY datetime(published_at) DESC LIMIT 1"
        ).fetchone()
        categories, categories_is_mock = _category_distribution_from_db(conn, total)

    by_source = [{"source": r["source"], "count": int(r["c"])} for r in by_source_rows]
    return {
        "db_path": str(DB_PATH),
        "article_total": total,
        "with_image": with_image,
        "without_image": max(0, total - with_image),
        "feedback_total": feedback_n,
        "profile_total": profile_n,
        "latest_published_at": (latest_pub["published_at"] if latest_pub else None),
        "by_source": by_source,
        "categories": categories,
        "categories_is_mock": categories_is_mock,
        "recent_articles": [dict(r) for r in latest],
        "recent_ingest_runs": list_ingest_runs(limit=8),
        "configured_sources": [
            {"name": s.name, "kind": s.kind, "tier": s.quality_tier, "url": s.url, "id": s.source_id}
            for s in get_news_sources()
        ],
    }


def list_news_articles_admin(*, limit: int = 30, offset: int = 0) -> dict[str, Any]:
    init_news_db()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total = int(conn.execute("SELECT COUNT(*) AS c FROM news_articles").fetchone()["c"])
        rows = conn.execute(
            """
            SELECT id, source, source_domain, source_tier, title, summary, url, image_url,
                   tags_csv, published_at, ingested_at, popularity
            FROM news_articles
            ORDER BY datetime(published_at) DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item["tags"] = split_tags_csv(r["tags_csv"])
        items.append(item)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_news_article_feed_item(article_id: int) -> dict[str, Any] | None:
    """按主键取一条资讯，供详情页打开。不依赖它是否还在首页前 40 条里。"""
    init_news_db()
    try:
        aid = int(article_id)
    except (TypeError, ValueError):
        return None
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, source, source_domain, source_tier, title, summary, url,
                   image_url, tags_csv, published_at, popularity
            FROM news_articles
            WHERE id=?
            """,
            (aid,),
        ).fetchone()
    if not row:
        return None
    tags = split_tags_csv(row["tags_csv"])
    item = {
        "id": row["id"],
        "kind": "news",
        "source": row["source"] or "资讯",
        "source_domain": row["source_domain"] or "",
        "source_tier": row["source_tier"],
        "title": row["title"] or "",
        "summary": row["summary"] or "",
        "url": row["url"] or "",
        "image_url": row["image_url"] or "",
        "tags_csv": row["tags_csv"] or "",
        "tags": tags,
        "published_at": row["published_at"] or "",
        "popularity": row["popularity"] or 0,
    }
    from rec.feedback import count_article_likes
    from services.poster import attach_poster

    item["like_count"] = count_article_likes(int(row["id"]))
    return attach_poster(item, kind="news", item_id=str(row["id"]), title=item["title"])


def list_coach_feed_items(limit: int = 12) -> list[dict[str, Any]]:
    """自有教学稿。发现页「教学」只在较大一页里按标签过滤，所以要单独附上。"""
    init_news_db()
    limit = max(1, min(int(limit), 20))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, source, source_domain, source_tier, title, summary, url,
                   image_url, tags_csv, published_at, popularity
            FROM news_articles
            WHERE source_domain='tenclip.coach'
            ORDER BY datetime(published_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    from rec.feedback import count_article_likes_batch
    from services.poster import attach_poster

    ids = [int(r["id"]) for r in rows]
    likes_map = count_article_likes_batch(ids)
    items: list[dict[str, Any]] = []
    for row in rows:
        tags = split_tags_csv(row["tags_csv"])
        item = {
            "id": row["id"],
            "kind": "news",
            "source": row["source"],
            "source_domain": row["source_domain"],
            "source_tier": row["source_tier"],
            "title": row["title"] or "",
            "summary": row["summary"] or "",
            "url": row["url"] or "",
            "image_url": row["image_url"] or "",
            "tags_csv": row["tags_csv"] or "",
            "tags": tags,
            "published_at": row["published_at"] or "",
            "popularity": row["popularity"] or 0,
            "like_count": likes_map.get(int(row["id"]), 0),
        }
        items.append(
            attach_poster(item, kind="news", item_id=str(row["id"]), title=item["title"])
        )
    return items


# 推荐子系统已迁至 rec/；此处 re-export 保持旧 import 路径兼容。
from rec import (  # noqa: E402
    RecommendInput,
    get_user_profile_tags,
    record_feedback,
    recommend_news,
    set_user_profile,
    suggest_tags,
)

__all__ = [
    "DB_PATH",
    "NewsSource",
    "RecommendInput",
    "TAG_KEYWORDS",
    "get_news_admin_overview",
    "get_news_sources",
    "get_user_profile_tags",
    "ingest_news",
    "init_news_db",
    "list_ingest_runs",
    "list_news_articles_admin",
    "news_ingest_health",
    "record_feedback",
    "recommend_news",
    "set_user_profile",
    "suggest_tags",
]