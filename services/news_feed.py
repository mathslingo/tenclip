from __future__ import annotations

import http.cookiejar
import json
import logging
import os
import re
import sqlite3
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from xml.etree import ElementTree as ET
import threading

from rec.tags import TAG_KEYWORDS, split_tags_csv

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
    """配置文件缺失或损坏时的兜底列表（与 config/news_sources.json 尽量保持一致）。"""
    return [
        NewsSource(
            name="CNN · Sport (RSS)",
            url="http://rss.cnn.com/rss/edition_sport.rss",
            kind="rss",
            quality_tier=2,
        ),
        NewsSource(
            name="BBC Sport · Tennis",
            url="https://feeds.bbci.co.uk/sport/tennis/rss.xml",
            kind="rss",
            quality_tier=2,
        ),
        NewsSource(
            name="Tennis.com · All news",
            url="https://www.tennis.com/news/all-news/",
            kind="html",
            quality_tier=3,
            parser="tennis_com_list",
        ),
        NewsSource(
            name="ATP Tour News",
            url="https://www.atptour.com/en/media/rss-feed/xml-feed",
            kind="rss",
            quality_tier=3,
        ),
        NewsSource(
            name="WTA News",
            url="https://www.wtatennis.com/rss/news",
            kind="rss",
            quality_tier=3,
        ),
        NewsSource(
            name="ESPN Tennis",
            url="https://www.espn.com/espn/rss/tennis/news",
            kind="rss",
            quality_tier=2,
        ),
        NewsSource(
            name="Google News · Tennis",
            url="https://news.google.com/rss/search?"
            + urlencode({"q": "ATP OR WTA OR tennis", "hl": "en-US", "gl": "US", "ceid": "US:en"}),
            kind="rss",
            quality_tier=1,
        ),
        NewsSource(
            name="ThePaper Sports",
            url="https://m.thepaper.cn/list_25599",
            kind="html",
            quality_tier=2,
            parser="thepaper_list",
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


def _parse_thepaper_html(source: NewsSource, html: str, cap: int) -> list[dict[str, Any]]:
    """解析澎湃列表页：从 HTML/内嵌 JSON 中提取 newsDetail_forward_* 与标题。"""
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
    for cid in ids_ordered:
        full = f"https://www.thepaper.cn/newsDetail_forward_{cid}"
        if full in seen_url:
            continue
        seen_url.add(full)
        title = _title_near(cid) or f"澎湃新闻 · 文章 {cid}"
        tags = _infer_tags(title, "", source)
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
                "published_at": _to_iso(_utc_now()),
                "ingested_at": _to_iso(_utc_now()),
            }
        )
        if len(out) >= cap:
            break
    return out


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


def ingest_news(limit_per_source: int = 20) -> dict[str, Any]:
    init_news_db()
    started = _to_iso(_utc_now())
    inserted = 0
    touched_sources: list[str] = []
    failed_sources: list[dict[str, str]] = []
    per_source_deadline = news_source_total_timeout_sec()
    http_cap = news_http_timeout_sec()
    with sqlite3.connect(DB_PATH) as conn:
        for source in get_news_sources():
            rows: list[dict[str, Any]] = []
            try:
                rows = _run_source_with_timeout(source, limit_per_source, per_source_deadline)
            except FuturesTimeoutError:
                msg = f"source timeout (>{per_source_deadline:.0f}s)"
                logger.warning("ingest source timeout: %s", source.name)
                failed_sources.append({"source": source.name, "error": msg})
                continue
            except Exception as exc:
                logger.warning("ingest source failed: %s %s", source.name, exc)
                failed_sources.append({"source": source.name, "error": str(exc)})
                continue
            if not rows:
                failed_sources.append({"source": source.name, "error": "no rows parsed"})
                continue
            touched_sources.append(source.name)
            for row in rows:
                cur = conn.execute(
                    """
                    INSERT INTO news_articles (
                        source, source_domain, source_tier, title, summary, url, image_url, tags_csv, published_at, ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        source=excluded.source,
                        source_domain=excluded.source_domain,
                        source_tier=excluded.source_tier,
                        title=excluded.title,
                        summary=excluded.summary,
                        image_url=excluded.image_url,
                        tags_csv=excluded.tags_csv,
                        published_at=excluded.published_at,
                        ingested_at=excluded.ingested_at
                    """,
                    (
                        row["source"],
                        row["source_domain"],
                        row["source_tier"],
                        row["title"],
                        row["summary"],
                        row["url"],
                        row["image_url"],
                        row["tags_csv"],
                        row["published_at"],
                        row["ingested_at"],
                    ),
                )
                inserted += int(cur.rowcount > 0)
        conn.commit()
    finished = _to_iso(_utc_now())
    result = {
        "inserted_or_updated": inserted,
        "sources": touched_sources,
        "failed": failed_sources,
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
    "record_feedback",
    "recommend_news",
    "set_user_profile",
    "suggest_tags",
]