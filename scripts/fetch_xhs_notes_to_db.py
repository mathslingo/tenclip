#!/usr/bin/env python3
"""按 explore URL 无 Cookie 抓取小红书笔记 meta，打印到 stdout 供人工校验；可选写入 Core API 库 `api_xhs_notes`。

用法（仓库根目录）::

    # 默认使用 data/xhs_cookie.txt；仅打印（不写库）
    python3 scripts/fetch_xhs_notes_to_db.py \\
      "https://www.xiaohongshu.com/explore/6912f396000000000700aca9"

    # 多条 + 从文件读 URL（每行一条）
    python3 scripts/fetch_xhs_notes_to_db.py --urls-file data/xhs_urls.txt

    # 校验无误后写入 SQLite（与 Core API 共用 `data/core_api.db`）
    python3 scripts/fetch_xhs_notes_to_db.py --commit URL1 URL2

默认读取 `data/xhs_cookie.txt`；无 Cookie 校验时设置 `TENCLIP_XHS_NO_COOKIE=1`。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 默认使用 Cookie；仅当显式 TENCLIP_XHS_NO_COOKIE=1 时禁用


def _load_urls_file(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        u = raw.strip()
        if u and not u.startswith("#"):
            lines.append(u)
    return lines


def _print_block(url: str, data: dict | None, err: str | None) -> None:
    print("=" * 72)
    print("URL:", url)
    if err:
        print("STATUS: FAIL")
        print("ERROR:", err)
        return
    assert data is not None
    print("STATUS: OK")
    print("title:", data.get("title"))
    print("image:", data.get("image"))
    print("description (摘要):", (data.get("description") or "")[:800])
    print("body (与 description 同源):", (data.get("body") or "")[:800])
    print("tags:", json.dumps(data.get("tags") or [], ensure_ascii=False))
    print("=" * 72)


async def _fetch_one(url: str) -> tuple[str, dict | None, str | None]:
    from fastapi import HTTPException

    from subprojects.core_api.xhs_preview import _coerce_note_url, fetch_xhs_note_preview

    try:
        safe = _coerce_note_url(url)
    except ValueError as e:
        return url.strip(), None, str(e)
    try:
        meta = await fetch_xhs_note_preview(safe)
        return safe, meta, None
    except HTTPException as e:
        return safe, None, str(e.detail)


def _upsert(session, safe_url: str, data: dict) -> None:
    from sqlalchemy import select

    from subprojects.core_api import models

    nid = safe_url.rstrip("/").split("/")[-1].lower()
    tags_json = json.dumps(data.get("tags") or [], ensure_ascii=False)
    now = datetime.now(timezone.utc)
    row = session.scalar(select(models.XhsCachedNote).where(models.XhsCachedNote.note_id == nid))
    body = data.get("body") or data.get("description")
    if row:
        row.explore_url = safe_url
        row.title = data.get("title")
        row.body = body
        row.image_url = data.get("image")
        row.tags_json = tags_json
        row.fetched_at = now
    else:
        session.add(
            models.XhsCachedNote(
                note_id=nid,
                explore_url=safe_url,
                title=data.get("title"),
                body=body,
                image_url=data.get("image"),
                tags_json=tags_json,
                fetched_at=now,
            )
        )


async def _main_async(urls: list[str], commit: bool) -> int:
    from subprojects.core_api.db import Base, SessionLocal, engine
    from subprojects.core_api import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    rc = 0
    to_save: list[tuple[str, dict]] = []
    for url in urls:
        safe, meta, err = await _fetch_one(url)
        _print_block(safe, meta, err)
        if err:
            rc = 1
        elif meta:
            to_save.append((safe, meta))

    if commit and to_save:
        db = SessionLocal()
        try:
            for safe, meta in to_save:
                _upsert(db, safe, meta)
            db.commit()
            print(f"\n[commit] 已写入 {len(to_save)} 条到 api_xhs_notes。", file=sys.stderr)
        except Exception as e:
            db.rollback()
            print(f"\n[commit] 失败: {e}", file=sys.stderr)
            return 1
        finally:
            db.close()
    elif commit and not to_save:
        print("\n[commit] 无成功条目，跳过写入。", file=sys.stderr)

    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取小红书 explore 笔记 meta 并打印；可选 --commit 入库")
    ap.add_argument("urls", nargs="*", help="explore 完整 URL")
    ap.add_argument("--urls-file", type=Path, help="每行一条 URL 的文本文件")
    ap.add_argument("--commit", action="store_true", help="将成功抓取的条目 upsert 到 api_xhs_notes")
    args = ap.parse_args()

    urls: list[str] = list(args.urls)
    if args.urls_file:
        urls.extend(_load_urls_file(args.urls_file))
    urls = [u.strip() for u in urls if u.strip()]
    if not urls:
        ap.print_help()
        print("\n请提供至少一个 URL，或使用 --urls-file。", file=sys.stderr)
        return 2

    return asyncio.run(_main_async(urls, args.commit))


if __name__ == "__main__":
    raise SystemExit(main())
