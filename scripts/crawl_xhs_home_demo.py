#!/usr/bin/env python3
"""首页四条 Demo 笔记：用 urllib 拉 explore HTML，按 xhs_crab 思路抽 og:* meta。

写入 data/xhs_demo_urllib_meta.json（与根目录 xhs_crab.py 的 data/xhs_crab_meta.json 区分）。

仓库根执行: python3 scripts/crawl_xhs_home_demo.py
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

_REPO = Path(__file__).resolve().parents[1]
OUT = _REPO / "data" / "xhs_demo_urllib_meta.json"

NOTE_IDS = [
    "6912f396000000000700aca9",
    "69dd7f1d000000001b022940",
    "696e4c6c0000000021029806",
    "697f00b6000000000e00cb66",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def get_meta(html: str, prop: str) -> str:
    esc = re.escape(prop)
    m = re.search(
        rf'<meta[^>]+(?:property|name)=["\']{esc}["\'][^>]+content=["\']([^"\']*)["\']',
        html,
        re.I,
    )
    if not m:
        m = re.search(
            rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{esc}["\']',
            html,
            re.I,
        )
    return m.group(1) if m else ""


def fetch_note(nid: str) -> dict:
    url = f"https://www.xiaohongshu.com/explore/{nid}"
    try:
        req = Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"tax": "home-demo", "nid": nid, "url": url, "error": str(e), "ok": False}

    title = get_meta(html, "og:title")
    image = get_meta(html, "og:image")
    likes = get_meta(html, "og:xhs:note_like")
    duration = get_meta(html, "og:videotime")
    note_type = get_meta(html, "og:xhs:note_type")
    out = {
        "tax": "home-demo",
        "nid": nid,
        "url": url,
        "title": title,
        "image": image,
        "likes": likes,
        "duration": duration,
        "note_type": note_type,
        "ok": bool(title),
    }
    if not out["ok"]:
        out["reason"] = "empty og:title (likely wall / need cookie or residential IP)"
        il = (image or "").lower()
        if "picasso-static" in il or "fe-platform" in il:
            out["reason"] += "; og:image is fe placeholder, not note cover"
    return out


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fetch_note, nid): nid for nid in NOTE_IDS}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            if r.get("ok"):
                t = (r.get("title") or "")[:60]
                print(f"OK  {r['nid']}  {t}")
            else:
                msg = (r.get("error") or r.get("reason") or "")[:120]
                print(f"ERR {r['nid']}  {msg}")

    results.sort(key=lambda x: NOTE_IDS.index(x["nid"]) if x["nid"] in NOTE_IDS else 99)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\nWrote {OUT}  ({ok}/{len(NOTE_IDS)} ok)")
    return 0 if ok == len(NOTE_IDS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
