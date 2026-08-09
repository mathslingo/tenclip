#!/usr/bin/env python3
"""Parse already-saved live-tennis homepage HTML (no network)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "live_tennis_probe"
HTML = DIR / "latest_home.html"
OUT = DIR / "latest_items.json"


def main() -> None:
    if not HTML.is_file():
        raise SystemExit(f"missing {HTML}; run probe_live_tennis_gentle.py first")
    text = HTML.read_text(encoding="utf-8", errors="ignore")
    blocks = re.findall(
        r'class="cHomeWheelDescText">(.*?)</div>',
        text,
        flags=re.S,
    )
    items: list[dict] = []
    seen: set[str] = set()
    for b in blocks:
        title = re.sub(r"<br\s*/?>", " ", b, flags=re.I)
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"\s+", " ", title).strip()
        if not title or title in seen:
            continue
        if "生日快乐" in title:
            continue
        seen.add(title)
        items.append(
            {
                "title": title,
                "summary": title,
                "source": "Live Tennis",
                "url": "https://www.live-tennis.cn/zh/home",
                "tags": ["赛事"],
            }
        )
    payload = {
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "html_path": str(HTML),
        "count": len(items),
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} count={len(items)}")
    for it in items[:15]:
        print("-", it["title"][:100])


if __name__ == "__main__":
    main()
