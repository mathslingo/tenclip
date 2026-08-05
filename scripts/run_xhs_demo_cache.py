#!/usr/bin/env python3
"""LF-safe demo: print 4 explore URLs -> commit to api_xhs_notes -> print DB rows.

Avoids bash + CRLF issues on Windows-saved .sh files. Run from repo root::

    python3 scripts/run_xhs_demo_cache.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_DB = _REPO / "data" / "core_api.db"

URLS = [
    "https://www.xiaohongshu.com/explore/6912f396000000000700aca9",
    "https://www.xiaohongshu.com/explore/69dd7f1d000000001b022940",
    "https://www.xiaohongshu.com/explore/696e4c6c0000000021029806",
    "https://www.xiaohongshu.com/explore/697f00b6000000000e00cb66",
]


def _load_fetch_module():
    path = _REPO / "scripts" / "fetch_xhs_notes_to_db.py"
    spec = importlib.util.spec_from_file_location("fetch_xhs_notes_to_db", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    os.environ.setdefault("TENCLIP_XHS_NO_COOKIE", "1")
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))

    mod = _load_fetch_module()

    print("=== 1) print only (verify) ===")
    rc1 = asyncio.run(mod._main_async(URLS, False))
    print("")
    print("=== 2) commit to api_xhs_notes ===")
    rc2 = asyncio.run(mod._main_async(URLS, True))

    print("")
    print("=== 3) last 8 rows in api_xhs_notes ===")
    if not _DB.is_file():
        print(f"(no db file at {_DB})", file=sys.stderr)
        return max(rc1, rc2, 1)
    con = sqlite3.connect(str(_DB))
    try:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='api_xhs_notes'"
        )
        if cur.fetchone() is None:
            print(
                "table api_xhs_notes missing; run Core API once or: "
                "python3 -c \"from subprojects.core_api.db import Base, engine; "
                "from subprojects.core_api import models; Base.metadata.create_all(bind=engine)\"",
                file=sys.stderr,
            )
            return max(rc1, rc2, 1)
        rows = con.execute(
            """SELECT note_id, title,
                      substr(COALESCE(body,''),1,80),
                      substr(COALESCE(image_url,''),1,60)
               FROM api_xhs_notes ORDER BY fetched_at DESC LIMIT 8"""
        ).fetchall()
        for row in rows:
            print(row)
    finally:
        con.close()

    return max(rc1, rc2)


if __name__ == "__main__":
    raise SystemExit(main())
