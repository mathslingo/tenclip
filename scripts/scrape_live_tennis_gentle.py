#!/usr/bin/env python3
"""
温和探测 live-tennis.cn：低频请求、随机 sleep，先落盘原始 HTML + 解析结果。
默认只请求首页 1 次；加 --follow N 才会再请求少量内链（每条间隔 2.5~5.5s）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "live_tennis_samples"
HOME_URL = "https://www.live-tennis.cn/zh/home"


def _sleep(lo: float = 2.5, hi: float = 5.5, reason: str = "") -> None:
    sec = random.uniform(lo, hi)
    msg = f"sleep {sec:.1f}s"
    if reason:
        msg += f" ({reason})"
    print(msg, flush=True)
    time.sleep(sec)


def fetch(url: str, timeout: float = 25.0) -> tuple[int, str, bytes]:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.live-tennis.cn/",
            "Connection": "close",
            "Cache-Control": "no-cache",
        },
    )
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
        return int(getattr(resp, "status", 200) or 200), (resp.headers.get("Content-Type") or ""), raw


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_home_feed(html: str, base_url: str) -> list[dict]:
    """
    首页动态流：恭喜…夺冠/进入TOP… 等短讯。
    站点未必每条都有独立详情 URL，优先抽标题+日期+赛事地点。
    """
    items: list[dict] = []
    seen: set[str] = set()

    # 常见结构：文本块含「恭喜」与日期 2026/07/20
    # 用较宽松的分段：按「恭喜」切开
    parts = re.split(r"(?=恭喜\s)", html)
    for part in parts:
        if "恭喜" not in part[:20] and not part.strip().startswith("恭喜"):
            # split 后第一段可能是页头
            if "恭喜" not in part[:200]:
                continue
        text = _clean(part[:800])
        if "恭喜" not in text:
            continue
        # 标题：从「恭喜」到日期或过长截断
        m = re.search(
            r"(恭喜[^0-9]{6,120}?)(?:\d{4}/\d{1,2}/\d{1,2}|祝 |基本信息|搜索热度|$)",
            text,
        )
        title = (m.group(1) if m else text[:80]).strip(" ·-，,")
        title = re.sub(r"\s+", " ", title)
        if len(title) < 8 or title in seen:
            continue
        if title.startswith("恭喜") and len(title) > 120:
            title = title[:120]
        dm = re.search(r"(20\d{2}/\d{1,2}/\d{1,2})", text)
        date_s = dm.group(1) if dm else ""
        # 粗提取地点/赛事（日期后短词）
        place = ""
        if dm:
            after = text[dm.end() : dm.end() + 40]
            pm = re.search(r"([^\d]{2,30})", after)
            if pm:
                place = pm.group(1).strip(" ·-|")
        # 尝试同块内链接
        hrefs = re.findall(r"""href=["']([^"']+)["']""", part[:2000])
        link = ""
        for h in hrefs:
            if h.startswith("#") or "javascript:" in h:
                continue
            full = urljoin(base_url, h)
            host = (urlparse(full).hostname or "").lower()
            if "live-tennis.cn" in host and "/zh/" in full:
                link = full
                break
        if not link:
            # 无详情页时用首页锚点式伪 URL，保证入库唯一
            digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]
            link = f"{HOME_URL}#lt-{digest}"

        tags = []
        blob = title + place
        if re.search(r"ATP|男子", blob, re.I):
            tags.append("ATP")
        if re.search(r"WTA|女子", blob, re.I):
            tags.append("WTA")
        if re.search(r"夺冠|决赛|温网|法网|美网|澳网|排名|TOP", blob, re.I):
            tags.append("赛事")
        tags = list(dict.fromkeys(tags)) or ["赛事"]

        seen.add(title)
        items.append(
            {
                "title": title,
                "summary": place,
                "url": link,
                "published_hint": date_s,
                "tags": tags,
                "source": "Live Tennis CN",
            }
        )
    return items


def parse_nav_links(html: str, base_url: str) -> list[str]:
    hrefs = re.findall(r"""href=["']([^"']+)["']""", html)
    out: list[str] = []
    seen: set[str] = set()
    for h in hrefs:
        full = urljoin(base_url, h)
        host = (urlparse(full).hostname or "").lower()
        if "live-tennis.cn" not in host:
            continue
        path = urlparse(full).path or ""
        if not path.startswith("/zh/"):
            continue
        # 排除明显静态/登录
        if any(x in path for x in ("login", "static", "assets", ".")):
            continue
        if full in seen:
            continue
        seen.add(full)
        out.append(full)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--follow", type=int, default=0, help="首页后再跟进多少个站内链接（默认 0）")
    ap.add_argument("--save-db", action="store_true", help="解析结果写入 news_feed.db")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"gentle fetch start {ts}", flush=True)
    _sleep(1.2, 2.2, "warm-up before first request")

    code, ctype, raw = fetch(HOME_URL)
    html = raw.decode("utf-8", "ignore")
    raw_path = OUT_DIR / f"home_{ts}.html"
    raw_path.write_bytes(raw)
    print(f"home HTTP {code} ctype={ctype[:40]} bytes={len(raw)} -> {raw_path}", flush=True)

    feed = parse_home_feed(html, HOME_URL)
    nav = parse_nav_links(html, HOME_URL)
    result = {
        "fetched_at": ts,
        "home_url": HOME_URL,
        "http": code,
        "feed_count": len(feed),
        "feed_items": feed[:40],
        "nav_sample": nav[:30],
        "markers": {
            "__NEXT_DATA__": "__NEXT_DATA__" in html,
            "__NUXT__": "__NUXT__" in html,
            "恭喜": html.count("恭喜"),
        },
        "followed": [],
    }
    print(f"parsed feed_items={len(feed)} nav_links={len(nav)} 恭喜_count={html.count('恭喜')}", flush=True)
    for it in feed[:8]:
        print(f"  - {it['title'][:70]} | {it.get('published_hint')} | {it.get('summary','')[:20]}", flush=True)

    follow_n = max(0, min(int(args.follow), 5))
    for i, link in enumerate(nav[:follow_n]):
        _sleep(2.8, 5.8, f"before follow {i+1}/{follow_n}")
        try:
            c2, _, raw2 = fetch(link)
            name = re.sub(r"[^\w\-]+", "_", urlparse(link).path.strip("/"))[:80] or f"page{i}"
            p = OUT_DIR / f"follow_{ts}_{name}.html"
            p.write_bytes(raw2)
            result["followed"].append({"url": link, "http": c2, "bytes": len(raw2), "path": str(p)})
            print(f"follow OK {c2} {link} -> {p.name}", flush=True)
        except Exception as exc:
            result["followed"].append({"url": link, "error": f"{type(exc).__name__}: {exc}"})
            print(f"follow FAIL {link}: {exc}", flush=True)
            _sleep(4.0, 7.0, "backoff after error")

    json_path = OUT_DIR / f"parse_{ts}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {json_path}", flush=True)

    if args.save_db and feed:
        import sys

        sys.path.insert(0, str(ROOT))
        from services.news_feed import DB_PATH, _to_iso, _utc_now, init_news_db
        import sqlite3

        init_news_db()
        inserted = 0
        with sqlite3.connect(DB_PATH) as conn:
            for it in feed:
                pub = it.get("published_hint") or ""
                if re.match(r"20\d{2}/\d{1,2}/\d{1,2}", pub):
                    y, m, d = pub.split("/")
                    published_at = f"{int(y):04d}-{int(m):02d}-{int(d):02d}T12:00:00+00:00"
                else:
                    published_at = _to_iso(_utc_now())
                cur = conn.execute(
                    """
                    INSERT INTO news_articles (
                        source, source_domain, source_tier, title, summary, url, image_url,
                        tags_csv, published_at, ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        title=excluded.title,
                        summary=excluded.summary,
                        tags_csv=excluded.tags_csv,
                        published_at=excluded.published_at,
                        ingested_at=excluded.ingested_at
                    """,
                    (
                        "Live Tennis CN",
                        "live-tennis.cn",
                        3,
                        it["title"],
                        it.get("summary") or "",
                        it["url"],
                        "",
                        ",".join(it.get("tags") or []),
                        published_at,
                        _to_iso(_utc_now()),
                    ),
                )
                inserted += int(cur.rowcount > 0)
            conn.commit()
        print(f"db upsert touched~={inserted} path={DB_PATH}", flush=True)

    print("done (gentle)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
