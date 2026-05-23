from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NoteInfo:
    """单条小红书 explore 笔记的基本信息。"""

    note_id: str
    explore_url: str
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    tags: list[str] = field(default_factory=list)
    likes: str | None = None
    note_type: str | None = None

    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id,
            "explore_url": self.explore_url,
            "title": self.title,
            "description": self.description,
            "image_url": self.image_url,
            "tags": list(self.tags),
            "likes": self.likes,
            "note_type": self.note_type,
        }


class NoteFetchError(Exception):
    """抓取或解析失败。"""

    def __init__(self, note_id: str, message: str, *, status_code: int | None = None) -> None:
        self.note_id = note_id
        self.status_code = status_code
        super().__init__(f"{note_id}: {message}")
