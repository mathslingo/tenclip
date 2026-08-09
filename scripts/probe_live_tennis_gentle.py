#!/usr/bin/env python3
"""温和探测 live-tennis.cn：少量请求 + sleep，结果落盘。

用法:
  python scripts/probe_live_tennis_gentle.py
"""
from __future__ import annotations

import json
import random
import re
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "live_tennis_probe"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def _sleep(lo: float = 1.2, hi: float = 2.8) -> None:
    delay = random.uniform(lo, hi)
    print(f"  sleep {delay:.2f}s …")
    time.sleep(delay)


def fetch(url: str, timeout: float = 20.0) -> dict:
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
            raw = resp.read(800_000)
            return {
                "ok": True,
                "url": url,
                "final_url": resp.geturl(),
                "http": getattr(resp, "status", 200),
                "ctype": (resp.headers.get("Content-Type") or "")[:80],
                "bytes": len(raw),
                "sec": round(time.time() - t0, 2),
                "body": raw.decode("utf-8", "ignore"),
                "error": "",
            }
    except HTTPError as e:
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http": int(e.code),
            "ctype": "",
            "bytes": 0,
            "sec": round(time.time() - t0, 2),
            "body": "",
            "error": f"HTTP {e.code}",
        }
    except URLError as e:
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http": 0,
            "ctype": "",
            "bytes": 0,
            "sec": round(time.time() - t0, 2),
            "body": "",
            "error": str(e.reason),
        }
    except Exception as e:
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http": 0,
            "ctype": "",
            "bytes": 0,
            "sec": round(time.time() - t0, 2),
            "body": "",
            "error": f"{type(e).__name__}: {e}",
        }


def extract_feedish(html: str) -> list[dict]:
    """从首页抽 cHomeWheelDescText 动态条目。"""
    items: list[dict] = []
    seen: set[str] = set()
    blocks = re.findall(
        r'class="cHomeWheelDescText">(.*?)</div>',
        html,
        flags=re.S,
    )
    for b in blocks:
        title = re.sub(r"<br\s*/?>", " ", b, flags=re.I)
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"\s+", " ", title).strip()
        if not title or title in seen:
            continue
        if "生日快乐" in title:
            continue
        seen.add(title)
        items.append(
            {
                "title": title,
                "summary": title,
                "source": "Live Tennis",
                "url": "https://www.live-tennis.cn/zh/home",
                "tags": ["赛事"],
            }
        )
    return items[:80]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # 只请求 1 个页面，避免频繁访问
    url = "https://www.live-tennis.cn/zh/home"
    print(f"GET {url}")
    _sleep(0.8, 1.5)
    res = fetch(url)
    meta = {k: v for k, v in res.items() if k != "body"}
    print(
        f"  ok={res['ok']} http={res['http']} bytes={res['bytes']} "
        f"sec={res['sec']} err={res['error'] or '-'}"
    )

    html_path = OUT_DIR / f"home_{stamp}.html"
    meta_path = OUT_DIR / f"home_{stamp}.meta.json"
    items_path = OUT_DIR / f"home_{stamp}.items.json"
    latest_html = OUT_DIR / "latest_home.html"
    latest_items = OUT_DIR / "latest_items.json"

    if res["ok"] and res["body"]:
        html_path.write_text(res["body"], encoding="utf-8")
        latest_html.write_text(res["body"], encoding="utf-8")
        items = extract_feedish(res["body"])
        payload = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "count": len(items),
            "items": items,
        }
        items_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        latest_items.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  extracted items: {len(items)}")
        for it in items[:8]:
            print(f"   - {it.get('date','')} {it['title'][:70]}")
    else:
        items = []

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved under {OUT_DIR}")
    # 结束后再休息一下，模拟人浏览停顿
    _sleep(1.0, 2.0)
    print("done")


if __name__ == "__main__":
    main()
