#!/usr/bin/env python3
"""调试 GET /matches 是否 500：仓库根目录 python3 scripts/debug_matches_route.py"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from starlette.testclient import TestClient

from subprojects.core_api.app import create_app


def main() -> int:
    app = create_app()
    c = TestClient(app)
    r = c.get("/matches?page=1&page_size=32")
    print("status", r.status_code)
    print(r.text[:4000])
    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
