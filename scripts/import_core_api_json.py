#!/usr/bin/env python3
"""
从 JSON 批量导入 subprojects/core_api 数据库（新闻、比赛、球员；可选视频）。

用法（仓库根目录）：
  python scripts/import_core_api_json.py path/to/data.json
  python scripts/import_core_api_json.py path/to/data.json --dry-run

JSON 顶层结构示例：
{
  "players": [
    {
      "id": "可选 UUID",
      "display_name": "必填",
      "country_code": "可选",
      "ranking_points": 3500.0,
      "created_at": "可选 ISO8601"
    }
  ],
  "matches": [
    {
      "id": "可选",
      "name": "可选",
      "tournament": "可选",
      "event_round": "可选",
      "home_side": "可选",
      "away_side": "可选",
      "player1_id": "可选 UUID，须已存在 players",
      "player2_id": "可选 UUID",
      "score": "可选，如 6-4 6-3",
      "venue": "可选",
      "scheduled_at": "可选 ISO8601",
      "status": "可选，默认 scheduled"
    }
  ],
  "news": [
    {
      "id": "可选",
      "title": "必填",
      "summary": "可选",
      "body": "可选，正文；也可用 content",
      "tags": "可选，字符串或数组；也可用 tag_list 数组",
      "players": "可选，字符串或数组；也可用 player_names",
      "source_url": "可选",
      "published_at": "可选 ISO8601"
    }
  ],
  "videos": [
    {
      "id": "可选",
      "title": "可选",
      "storage_uri": "必填",
      "duration_sec": 120,
      "match_id": "可选",
      "primary_player_id": "可选"
    }
  ]
}

导入顺序：players → matches → news → videos（保证外键）。
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from subprojects.core_api.db import Base, SessionLocal, engine  # noqa: E402
from subprojects.core_api import models  # noqa: E402


def _parse_uuid(val: Any, field: str) -> uuid.UUID | None:
    if val is None or val == "":
        return None
    try:
        return uuid.UUID(str(val))
    except ValueError as e:
        raise ValueError(f"invalid UUID for {field}: {val!r}") from e


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    s = str(val).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _player_row(raw: dict[str, Any], index: int) -> models.Player:
    if not raw.get("display_name"):
        raise ValueError(f"players[{index}]: display_name is required")
    pid = _parse_uuid(raw.get("id"), f"players[{index}].id") or uuid.uuid4()
    return models.Player(
        id=pid,
        display_name=str(raw["display_name"]),
        country_code=(str(raw["country_code"]) if raw.get("country_code") else None),
        ranking_points=(
            float(raw["ranking_points"]) if raw.get("ranking_points") is not None else None
        ),
        created_at=_parse_dt(raw.get("created_at")) or datetime.now(timezone.utc),
    )


def _match_row(raw: dict[str, Any], index: int) -> models.Match:
    mid = _parse_uuid(raw.get("id"), f"matches[{index}].id") or uuid.uuid4()
    return models.Match(
        id=mid,
        name=(str(raw["name"]) if raw.get("name") is not None else None),
        tournament=(str(raw["tournament"]) if raw.get("tournament") is not None else None),
        event_round=(str(raw["event_round"]) if raw.get("event_round") is not None else None),
        home_side=(str(raw["home_side"]) if raw.get("home_side") is not None else None),
        away_side=(str(raw["away_side"]) if raw.get("away_side") is not None else None),
        player1_id=_parse_uuid(raw.get("player1_id"), f"matches[{index}].player1_id"),
        player2_id=_parse_uuid(raw.get("player2_id"), f"matches[{index}].player2_id"),
        score=(str(raw["score"]) if raw.get("score") is not None else None),
        venue=(str(raw["venue"]) if raw.get("venue") is not None else None),
        scheduled_at=_parse_dt(raw.get("scheduled_at")),
        status=str(raw.get("status") or "scheduled"),
        created_at=_parse_dt(raw.get("created_at")) or datetime.now(timezone.utc),
    )


def _news_row(raw: dict[str, Any], index: int) -> models.News:
    if not raw.get("title"):
        raise ValueError(f"news[{index}]: title is required")
    nid = _parse_uuid(raw.get("id"), f"news[{index}].id") or uuid.uuid4()
    body = raw.get("body")
    if body is None and raw.get("content") is not None:
        body = raw.get("content")
    tags = raw.get("tags")
    if isinstance(tags, list):
        tags = ",".join(str(x) for x in tags)
    if tags is None and raw.get("tag_list") is not None:
        tags = (
            ",".join(str(x) for x in raw["tag_list"])
            if isinstance(raw["tag_list"], list)
            else raw.get("tag_list")
        )
    players = raw.get("players")
    if isinstance(players, list):
        players = ",".join(str(x) for x in players)
    if players is None and raw.get("player_names") is not None:
        pn = raw.get("player_names")
        players = ",".join(str(x) for x in pn) if isinstance(pn, list) else pn
    return models.News(
        id=nid,
        title=str(raw["title"]),
        summary=(str(raw["summary"]) if raw.get("summary") is not None else None),
        body=(str(body) if body is not None else None),
        tags=(str(tags) if tags is not None else None),
        players=(str(players) if players is not None else None),
        source_url=(str(raw["source_url"]) if raw.get("source_url") is not None else None),
        published_at=_parse_dt(raw.get("published_at")),
        created_at=_parse_dt(raw.get("created_at")) or datetime.now(timezone.utc),
    )


def _video_row(raw: dict[str, Any], index: int) -> models.Video:
    if not raw.get("storage_uri"):
        raise ValueError(f"videos[{index}]: storage_uri is required")
    vid = _parse_uuid(raw.get("id"), f"videos[{index}].id") or uuid.uuid4()
    dur = raw.get("duration_sec")
    return models.Video(
        id=vid,
        title=(str(raw["title"]) if raw.get("title") is not None else None),
        storage_uri=str(raw["storage_uri"]),
        duration_sec=(int(dur) if dur is not None else None),
        match_id=_parse_uuid(raw.get("match_id"), f"videos[{index}].match_id"),
        primary_player_id=_parse_uuid(
            raw.get("primary_player_id"), f"videos[{index}].primary_player_id"
        ),
        created_at=_parse_dt(raw.get("created_at")) or datetime.now(timezone.utc),
    )


def _upsert(session: Any, row: Any) -> str:
    existing = session.get(type(row), row.id)
    if existing is None:
        session.add(row)
        return "inserted"
    for col in type(row).__mapper__.column_attrs:
        key = col.key
        if key == "id":
            continue
        setattr(existing, key, getattr(row, key))
    return "updated"


def _ensure_fk_player(session: Any, pid: uuid.UUID | None, ctx: str) -> None:
    if pid is None:
        return
    if session.get(models.Player, pid) is None:
        raise ValueError(f"{ctx}: player id {pid} not found; import players first or fix JSON")


def _ensure_fk_match(session: Any, mid: uuid.UUID | None, ctx: str) -> None:
    if mid is None:
        return
    if session.get(models.Match, mid) is None:
        raise ValueError(f"{ctx}: match id {mid} not found; import matches first or fix JSON")


def run_import(path: Path, *, dry_run: bool) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    stats: dict[str, Any] = {
        "file": str(path),
        "dry_run": dry_run,
        "players": {"inserted": 0, "updated": 0},
        "matches": {"inserted": 0, "updated": 0},
        "news": {"inserted": 0, "updated": 0},
        "videos": {"inserted": 0, "updated": 0},
    }

    try:
        players_in = payload.get("players") or []
        if not isinstance(players_in, list):
            raise ValueError('"players" must be a list')
        for i, raw in enumerate(players_in):
            if not isinstance(raw, dict):
                raise ValueError(f"players[{i}] must be an object")
            row = _player_row(raw, i)
            op = _upsert(session, row)
            stats["players"]["inserted" if op == "inserted" else "updated"] += 1

        matches_in = payload.get("matches") or []
        if not isinstance(matches_in, list):
            raise ValueError('"matches" must be a list')
        for i, raw in enumerate(matches_in):
            if not isinstance(raw, dict):
                raise ValueError(f"matches[{i}] must be an object")
            row = _match_row(raw, i)
            _ensure_fk_player(session, row.player1_id, f"matches[{i}].player1_id")
            _ensure_fk_player(session, row.player2_id, f"matches[{i}].player2_id")
            op = _upsert(session, row)
            stats["matches"]["inserted" if op == "inserted" else "updated"] += 1

        news_in = payload.get("news") or []
        if not isinstance(news_in, list):
            raise ValueError('"news" must be a list')
        for i, raw in enumerate(news_in):
            if not isinstance(raw, dict):
                raise ValueError(f"news[{i}] must be an object")
            row = _news_row(raw, i)
            op = _upsert(session, row)
            stats["news"]["inserted" if op == "inserted" else "updated"] += 1

        videos_in = payload.get("videos") or []
        if not isinstance(videos_in, list):
            raise ValueError('"videos" must be a list')
        for i, raw in enumerate(videos_in):
            if not isinstance(raw, dict):
                raise ValueError(f"videos[{i}] must be an object")
            row = _video_row(raw, i)
            _ensure_fk_match(session, row.match_id, f"videos[{i}].match_id")
            _ensure_fk_player(session, row.primary_player_id, f"videos[{i}].primary_player_id")
            op = _upsert(session, row)
            stats["videos"]["inserted" if op == "inserted" else "updated"] += 1

        if dry_run:
            session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Import core_api entities from JSON")
    parser.add_argument("json_file", type=Path, help="Path to JSON file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and run in a transaction, then rollback",
    )
    args = parser.parse_args()
    path = args.json_file.expanduser()
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 1
    try:
        stats = run_import(path, dry_run=args.dry_run)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(f"Import failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
