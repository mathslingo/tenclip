"""新笔记抓取模块的 HTTP 路由（与 xhs_preview 无关）。"""

from __future__ import annotations

import re

from fastapi import HTTPException, Query

from subprojects.xhs_note import NoteFetchError, fetch_note_by_id


def register_xhs_note_routes(application) -> None:
    @application.get("/api/utils/xhs-note-by-id")
    @application.get("/utils/xhs-note-by-id")
    def xhs_note_by_id(note_id: str = Query(..., min_length=24, max_length=24)):
        if not re.fullmatch(r"[0-9a-fA-F]{24}", note_id):
            raise HTTPException(status_code=400, detail="note_id must be 24 hex characters")
        try:
            info = fetch_note_by_id(note_id.lower())
            return info.to_dict()
        except NoteFetchError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
