"""按笔记 ID 抓取小红书笔记基本信息（需登录 Cookie）。

默认读取仓库 `data/xhs_cookie.txt`，或通过环境变量配置（见 `cookies` 模块）。

示例::

    from subprojects.xhs_note import fetch_note_by_id, NoteInfo

    note = fetch_note_by_id("69dd7f1d000000001b022940")
    print(note.title, note.image_url)
"""

from .client import fetch_note_by_id, fetch_notes_by_ids
from .cookies import cookie_status, load_cookies
from .models import NoteFetchError, NoteInfo

__all__ = [
    "NoteInfo",
    "NoteFetchError",
    "fetch_note_by_id",
    "fetch_notes_by_ids",
    "load_cookies",
    "cookie_status",
]
