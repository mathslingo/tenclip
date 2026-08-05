#!/usr/bin/env python3
"""tennis_news 抓取入口：fetch → parse → 落盘快照 + 入库。

用法：
    python -m tennis_news.ingest                 # 抓取、存快照、写入 DB
    python -m tennis_news.ingest --cap 60         # 最多取 60 条
    python -m tennis_news.ingest --no-db          # 只存快照，不写 DB
    python -m tennis_news.ingest --from-file X    # 离线：解析已保存的 HTML
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from tennis_news.live_tennis import HOME_URL, fetch_home, parse_home_items
from tennis_news.store import save_snapshot, upsert_rows


def run(
    *,
    cap: int = 80,
    write_db: bool = True,
    save_html: bool = True,
    from_file: str | None = None,
) -> dict[str, Any]:
    if from_file:
        html = Path(from_file).read_text(encoding="utf-8", errors="ignore")
        meta = {"ok": True, "http": 0, "bytes": len(html), "sec": 0.0, "error": "", "final_url": from_file}
    else:
        res = fetch_home()
        if not res["ok"] or not res["body"]:
            return {"ok": False, "error": res["error"] or "empty body", "http": res["http"]}
        html = res["body"]
        meta = res

    rows = parse_home_items(html, cap=cap)
    saved = save_snapshot(
        rows,
        source_url=meta.get("final_url") or HOME_URL,
        raw_html=html if (save_html and not from_file) else None,
    )
    inserted = upsert_rows(rows) if write_db else 0
    return {
        "ok": True,
        "http": meta.get("http"),
        "bytes": meta.get("bytes"),
        "sec": meta.get("sec"),
        "parsed": len(rows),
        "inserted_or_updated": inserted,
        "wrote_db": write_db,
        "snapshot": saved,
        "items": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="抓取 live-tennis.cn 首页新闻并入库")
    ap.add_argument("--cap", type=int, default=80, help="最多解析条数（默认 80）")
    ap.add_argument("--no-db", action="store_true", help="不写入 news_feed.db，只存快照")
    ap.add_argument("--no-html", action="store_true", help="不落盘原始 HTML")
    ap.add_argument("--from-file", type=str, default=None, help="离线解析指定 HTML 文件")
    args = ap.parse_args(argv)

    result = run(
        cap=args.cap,
        write_db=not args.no_db,
        save_html=not args.no_html,
        from_file=args.from_file,
    )
    if not result.get("ok"):
        print(f"FAILED http={result.get('http')} error={result.get('error')}", file=sys.stderr)
        return 1

    print(
        f"ok http={result['http']} bytes={result['bytes']} sec={result['sec']} "
        f"parsed={result['parsed']} db_upsert={result['inserted_or_updated']}"
    )
    for it in result["items"][:10]:
        print(f"  - {it['title'][:60]} | {it['summary'][:30]} | {it['tags_csv']}")
    snap = result["snapshot"]
    print(f"snapshot: {snap.get('latest_items')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
