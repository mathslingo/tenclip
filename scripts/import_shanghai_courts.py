#!/usr/bin/env python3
"""将 data/shanghai_tennis_data.json 导入 data/courts.db（仅网球）。"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.courts import import_shanghai_json, init_courts_db, courts_stats


def main() -> int:
    init_courts_db(auto_import=False)
    result = import_shanghai_json()
    print(result)
    print(courts_stats())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
