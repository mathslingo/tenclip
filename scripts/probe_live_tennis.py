#!/usr/bin/env python3
"""Probe live-tennis.cn page structure for news_feed HTML parser."""
from __future__ import annotations

import json
import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str) -> tuple[int, str, str]:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=20, context=ctx) as resp:
        raw = resp.read(400000)
        return getattr(resp, "status", 200), (resp.headers.get("Content-Type") or ""), raw.decode(
            "utf-8", "ignore"
        )


def main() -> None:
    urls = [
        "https://www.live-tennis.cn/zh/home",
        "https://www.live-tennis.cn/zh",
        "https://www.live-tennis.cn/",
        "https://www.live-tennis.cn/zh/news",
        "https://www.live-tennis.cn/en/home",
    ]
    report = []
    for u in urls:
        try:
            code, ctype, text = fetch(u)
            hrefs = re.findall(r"""href=["']([^"']+)["']""", text)
            interesting = [
                h
                for h in hrefs
                if any(
                    k in h.lower()
                    for k in (
                        "news",
                        "article",
                        "match",
                        "atp",
                        "wta",
                        "/zh/",
                        "detail",
                        "post",
                        "blog",
                        "ranking",
                        "tournament",
                    )
                )
            ]
            titles = re.findall(r"<h[1-3][^>]*>\s*([^<]{4,120})\s*</h[1-3]>", text, flags=re.I)
            json_blobs = re.findall(r"<script[^>]*>(\{.*?\})</script>", text, flags=re.I | re.S)
            item = {
                "url": u,
                "ok": True,
                "http": code,
                "ctype": ctype[:60],
                "bytes": len(text),
                "href_count": len(hrefs),
                "interesting": interesting[:40],
                "h_titles": titles[:20],
                "title": (re.search(r"<title>([^<]+)</title>", text, flags=re.I) or [None, ""])[1]
                if False
                else "",
            }
            tm = re.search(r"<title>([^<]+)</title>", text, flags=re.I)
            item["title"] = tm.group(1).strip() if tm else ""
            item["script_json_count"] = len(json_blobs)
            # look for __NEXT_DATA__ / nuxt
            for marker in ("__NEXT_DATA__", "__NUXT__", "window.__INITIAL", "application/ld+json"):
                item[marker] = marker in text
            report.append(item)
            print("OK", code, u, "hrefs", len(hrefs), "interesting", len(interesting), "h", len(titles))
            for h in interesting[:15]:
                print("  ", h[:160])
            for t in titles[:8]:
                print("  H:", t.strip()[:100])
        except Exception as e:
            print("FAIL", u, type(e).__name__, e)
            report.append({"url": u, "ok": False, "error": f"{type(e).__name__}: {e}"})

    out = ROOT / "data" / "live_tennis_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", out)


if __name__ == "__main__":
    main()
