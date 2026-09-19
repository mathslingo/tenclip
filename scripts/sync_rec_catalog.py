#!/usr/bin/env python3
"""把 social.notes 与 news_articles 回填到 data/rec_notes.db。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rec.catalog import backfill_rec_catalog, rec_catalog_stats  # noqa: E402


def main() -> int:
    stats = backfill_rec_catalog()
    print(json.dumps({**stats, **rec_catalog_stats()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
