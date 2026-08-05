#!/usr/bin/env python3
"""tennis_news 本地存储：JSON 快照 + upsert 到 news_feed.db。

复用 services.news_feed 的 SQLite schema（news_articles，UNIQUE(url)），
使 live-tennis.cn 的数据自动进入既有 API `/api/news/feed` 与小程序双列前端。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = _REPO_ROOT / "data" / "live_tennis_probe"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def save_snapshot(
    rows: list[dict[str, Any]],
    *,
    source_url: str,
    raw_html: str | None = None,
    snapshot_dir: Path = SNAPSHOT_DIR,
) -> dict[str, str]:
    """把解析结果落盘：时间戳文件 + latest_*，便于离线复现与调试。"""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "url": source_url,
        "count": len(rows),
        "items": rows,
    }
    items_path = snapshot_dir / f"home_{stamp}.items.json"
    latest_items = snapshot_dir / "latest_items.json"
    items_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_items.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    out = {"items_path": str(items_path), "latest_items": str(latest_items)}
    if raw_html:
        html_path = snapshot_dir / f"home_{stamp}.html"
        latest_html = snapshot_dir / "latest_home.html"
        html_path.write_text(raw_html, encoding="utf-8")
        latest_html.write_text(raw_html, encoding="utf-8")
        out["html_path"] = str(html_path)
        out["latest_html"] = str(latest_html)
    return out


def upsert_rows(rows: list[dict[str, Any]]) -> int:
    """把新闻行 upsert 进 news_feed.db，返回受影响条数。"""
    if not rows:
        return 0
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    # 延迟导入，避免与 services 的循环依赖
    from services.news_feed import DB_PATH, init_news_db

    init_news_db()
    touched = 0
    with sqlite3.connect(DB_PATH) as conn:
        for row in rows:
            cur = conn.execute(
                """
                INSERT INTO news_articles (
                    source, source_domain, source_tier, title, summary, url,
                    image_url, tags_csv, published_at, ingested_at
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
            touched += int(cur.rowcount > 0)
        conn.commit()
    return touched
