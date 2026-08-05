#!/usr/bin/env python3
"""Probe which tennis news sources are crawlable from this machine."""
from __future__ import annotations

import json
import ssl
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]


def probe(url: str, timeout: float = 12.0) -> dict:
    t0 = time.time()
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml, application/xml, text/html, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        },
    )
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(250000)
            code = getattr(resp, "status", 200)
            ctype = (resp.headers.get("Content-Type") or "")[:80]
            text = raw.decode("utf-8", "ignore")
            kind = "unknown"
            items = 0
            low = text.lower()
            if "<rss" in low or "<feed" in low or "xml" in ctype or "rss" in ctype:
                kind = "rss/xml"
                try:
                    root = ET.fromstring(raw)
                    items = len(root.findall(".//item")) + len(
                        root.findall(".//{http://www.w3.org/2005/Atom}entry")
                    )
                except Exception as exc:
                    kind = f"xml-broken:{type(exc).__name__}"
            elif "<html" in low or "text/html" in ctype:
                kind = "html"
                items = low.count("href=")
            return {
                "ok": True,
                "http": code,
                "sec": round(time.time() - t0, 2),
                "ctype": ctype,
                "bytes": len(raw),
                "kind": kind,
                "signal": items,
                "error": "",
            }
    except HTTPError as e:
        return {
            "ok": False,
            "http": int(e.code),
            "sec": round(time.time() - t0, 2),
            "ctype": "",
            "bytes": 0,
            "kind": "",
            "signal": 0,
            "error": f"HTTP {e.code}",
        }
    except URLError as e:
        return {
            "ok": False,
            "http": 0,
            "sec": round(time.time() - t0, 2),
            "ctype": "",
            "bytes": 0,
            "kind": "",
            "signal": 0,
            "error": str(e.reason),
        }
    except Exception as e:
        return {
            "ok": False,
            "http": 0,
            "sec": round(time.time() - t0, 2),
            "ctype": "",
            "bytes": 0,
            "kind": "",
            "signal": 0,
            "error": f"{type(e).__name__}: {e}",
        }


def main() -> None:
    cfg = json.loads((ROOT / "config" / "news_sources.json").read_text(encoding="utf-8"))
    configured = cfg["sources"]
    candidates = [
        {
            "id": "guardian_tennis",
            "name": "Guardian Tennis",
            "url": "https://www.theguardian.com/sport/tennis/rss",
            "kind": "rss",
        },
        {
            "id": "nyt_tennis",
            "name": "NYT Tennis",
            "url": "https://rss.nytimes.com/services/xml/rss/nyt/Tennis.xml",
            "kind": "rss",
        },
        {
            "id": "sky_sports_tennis",
            "name": "Sky Sports Tennis",
            "url": "https://www.skysports.com/rss/12040",
            "kind": "rss",
        },
        {
            "id": "wta_rss_xml",
            "name": "WTA news.xml",
            "url": "https://www.wtatennis.com/rss/news.xml",
            "kind": "rss",
        },
        {
            "id": "atp_xml_feed_alt",
            "name": "ATP xml-feed alt path",
            "url": "https://www.atptour.com/en/-/media/rss-feed/xml-feed",
            "kind": "rss",
        },
        {
            "id": "tennis_com_rss",
            "name": "Tennis.com /rss/news",
            "url": "https://www.tennis.com/rss/news",
            "kind": "rss",
        },
        {
            "id": "espn_tennis_http",
            "name": "ESPN Tennis http",
            "url": "http://www.espn.com/espn/rss/tennis/news",
            "kind": "rss",
        },
        {
            "id": "sina_tennis",
            "name": "Sina Tennis",
            "url": "https://sports.sina.com.cn/tennis/",
            "kind": "html",
        },
        {
            "id": "qq_tennis",
            "name": "QQ Sports tennis channel",
            "url": "https://sports.qq.com/tennis/",
            "kind": "html",
        },
        {
            "id": "163_tennis",
            "name": "163 tennis",
            "url": "https://sports.163.com/tennis/",
            "kind": "html",
        },
        {
            "id": "thepaper_list",
            "name": "ThePaper sports list",
            "url": "https://m.thepaper.cn/list_25599",
            "kind": "html",
        },
    ]

    rows = []
    print(f"{'group':10} {'id':22} {'ok':4} {'http':4} {'signal':7} detail")
    for group, items in (("config", configured), ("candidate", candidates)):
        for s in items:
            r = probe(s["url"])
            row = {
                "group": group,
                "id": s.get("id") or "",
                "name": s.get("name") or "",
                "enabled": s.get("enabled"),
                "url": s["url"],
                **r,
            }
            rows.append(row)
            detail = r["kind"] if r["ok"] else r["error"]
            print(
                f"{group:10} {(s.get('id') or s.get('name',''))[:22]:22} "
                f"{str(r['ok']):4} {r['http']:4} {r['signal']:7} {detail}"
            )

    out = ROOT / "data" / "news_source_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
