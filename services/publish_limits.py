"""Load shared publish limits from config/publish_limits.json."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _REPO_ROOT / "config" / "publish_limits.json"

_DEFAULTS: dict[str, Any] = {
    "note": {
        "max_images_per_note": 10,
        "max_notes_per_user_per_day": 10,
        "day_timezone": "Asia/Shanghai",
    }
}


def load_publish_limits() -> dict[str, Any]:
    data: dict[str, Any] = {"note": dict(_DEFAULTS["note"])}
    try:
        if _CONFIG_PATH.is_file():
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                note_raw = raw.get("note")
                if isinstance(note_raw, dict):
                    data["note"].update(note_raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    note = data["note"]
    note["max_images_per_note"] = max(1, int(note.get("max_images_per_note", 10)))
    note["max_notes_per_user_per_day"] = max(
        1, int(note.get("max_notes_per_user_per_day", 10))
    )
    note["day_timezone"] = str(note.get("day_timezone") or "Asia/Shanghai")
    return data


def note_max_images() -> int:
    return int(load_publish_limits()["note"]["max_images_per_note"])


def note_max_per_day() -> int:
    return int(load_publish_limits()["note"]["max_notes_per_user_per_day"])


def day_bounds_unix() -> tuple[float, float]:
    tz_name = str(load_publish_limits()["note"].get("day_timezone") or "Asia/Shanghai")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp()
