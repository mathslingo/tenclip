#!/usr/bin/env python3
"""按笔记 ID 抓取小红书笔记基本信息（使用 data/xhs_cookie.txt）。

仓库根目录执行::

    python3 scripts/xhs_note_fetch.py 69dd7f1d000000001b022940
    python3 scripts/xhs_note_fetch.py --ids-file data/xhs_notes.csv
    python3 scripts/xhs_note_fetch.py --json-out data/xhs_note_fetched.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from subprojects.xhs_note import NoteFetchError, NoteInfo, cookie_status, fetch_notes_by_ids


def _load_ids_from_csv(path: Path) -> list[str]:
    ids: list[str] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            nid = (row.get("note_id") or "").strip()
            if nid:
                ids.append(nid)
    return ids


def _print_note(item: NoteInfo | NoteFetchError) -> None:
    if isinstance(item, NoteFetchError):
        print(f"FAIL {item.note_id}: {item}")
        return
    print(f"OK   {item.note_id}")
    print(f"     title: {item.title}")
    print(f"     image: {(item.image_url or '')[:100]}")
    desc = (item.description or "")[:120]
    if desc:
        print(f"     desc:  {desc}")
    if item.tags:
        print(f"     tags:  {item.tags[:8]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="按笔记 ID 抓取小红书笔记（需 Cookie）")
    ap.add_argument("note_ids", nargs="*", help="24 位 hex 笔记 ID")
    ap.add_argument("--ids-file", type=Path, help="CSV，需含 note_id 列")
    ap.add_argument("--json-out", type=Path, help="写入 JSON 数组")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    ids = list(args.note_ids)
    if args.ids_file:
        ids.extend(_load_ids_from_csv(args.ids_file))
    ids = [i.strip() for i in ids if i.strip()]
    if not ids:
        ap.print_help()
        print("\n请提供至少一个 note_id 或 --ids-file", file=sys.stderr)
        return 2

    st = cookie_status()
    print("Cookie:", json.dumps(st, ensure_ascii=False))
    if st["cookie_count"] == 0:
        print("错误: 未加载 Cookie，请配置 data/xhs_cookie.txt", file=sys.stderr)
        return 1
    print()

    results = fetch_notes_by_ids(ids, max_workers=args.workers)
    ok = 0
    payload: list[dict] = []
    for item in results:
        _print_note(item)
        print()
        if isinstance(item, NoteInfo):
            ok += 1
            payload.append(item.to_dict())
        else:
            payload.append({"note_id": item.note_id, "error": str(item), "ok": False})

    print(f"成功: {ok}/{len(ids)}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {args.json_out}")
    return 0 if ok == len(ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
