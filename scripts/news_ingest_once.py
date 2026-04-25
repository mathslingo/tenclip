#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="TenClip 网坛新闻单次抓取任务")
    parser.add_argument("--limit-per-source", type=int, default=30, help="每个来源最多抓取条数")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    log_path = repo_root / "data" / "news_ingest_last_run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    from services.news_feed import ingest_news, init_news_db  # noqa: WPS433

    try:
        init_news_db()
        result = ingest_news(limit_per_source=max(1, min(args.limit_per_source, 120)))
        line = json.dumps(result, ensure_ascii=False)
        print(line, flush=True)
        return 0
    except Exception:
        logging.exception("news_ingest_once 失败")
        err_path = repo_root / "data" / "news_ingest_last_error.txt"
        err_path.write_text(traceback.format_exc(), encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
