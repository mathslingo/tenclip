"""Resumable chunk upload sessions for large mobile video files."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)

CHUNK_SIZE_BYTES = 2 * 1024 * 1024
SESSION_TTL_SEC = 6 * 3600

_SESSIONS: dict[str, "UploadSession"] = {}
_LOCK = threading.Lock()


@dataclass
class UploadSession:
    session_id: str
    purpose: str  # stroke | analyze
    dest_path: Path
    file_size: int
    total_chunks: int
    chunk_size: int
    meta: dict[str, Any]
    chunks_received: set[int] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)


def _upload_suffix(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in (".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"):
        return suffix
    return ".mp4"


def _prune_expired() -> None:
    now = time.time()
    expired = [
        sid
        for sid, s in _SESSIONS.items()
        if now - s.created_at > SESSION_TTL_SEC
    ]
    for sid in expired:
        sess = _SESSIONS.pop(sid, None)
        if sess is None:
            continue
        try:
            if sess.dest_path.exists():
                sess.dest_path.unlink(missing_ok=True)
            sess.dest_path.parent.rmdir()
        except OSError:
            pass


def create_session(
    *,
    repo_root: Path,
    purpose: str,
    file_size: int,
    filename: str,
    total_chunks: int,
    chunk_size: int,
    meta: dict[str, Any],
) -> dict[str, Any]:
    if purpose not in ("stroke", "analyze"):
        raise HTTPException(status_code=400, detail="purpose 须为 stroke 或 analyze")
    if file_size <= 0 or total_chunks <= 0 or chunk_size <= 0:
        raise HTTPException(status_code=400, detail="无效的文件大小或分片参数")

    _prune_expired()
    session_id = uuid.uuid4().hex
    suffix = _upload_suffix(filename)
    dest_dir = repo_root / "data" / "uploads" / "chunk_sessions" / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"video{suffix}"

    with dest_path.open("wb") as out:
        out.truncate(file_size)

    sess = UploadSession(
        session_id=session_id,
        purpose=purpose,
        dest_path=dest_path,
        file_size=file_size,
        total_chunks=total_chunks,
        chunk_size=chunk_size,
        meta=dict(meta),
    )
    with _LOCK:
        _SESSIONS[session_id] = sess
    logger.info(
        "chunk session %s purpose=%s size=%s chunks=%s",
        session_id,
        purpose,
        file_size,
        total_chunks,
    )
    return {
        "session_id": session_id,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
    }


def write_chunk(session_id: str, chunk_index: int, data: bytes) -> None:
    with _LOCK:
        sess = _SESSIONS.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="上传会话不存在或已过期")

    if chunk_index < 0 or chunk_index >= sess.total_chunks:
        raise HTTPException(status_code=400, detail="分片序号无效")

    offset = chunk_index * sess.chunk_size
    if offset >= sess.file_size and len(data) > 0:
        raise HTTPException(status_code=400, detail="分片偏移超出文件大小")

    with sess.dest_path.open("r+b") as out:
        out.seek(offset)
        out.write(data)

    with _LOCK:
        sess.chunks_received.add(chunk_index)


def take_session(session_id: str) -> UploadSession:
    with _LOCK:
        sess = _SESSIONS.pop(session_id, None)
    if sess is None:
        raise HTTPException(status_code=404, detail="上传会话不存在或已过期")
    if len(sess.chunks_received) != sess.total_chunks:
        raise HTTPException(
            status_code=400,
            detail=f"分片不完整 ({len(sess.chunks_received)}/{sess.total_chunks})",
        )
    actual = sess.dest_path.stat().st_size
    if actual != sess.file_size:
        raise HTTPException(status_code=400, detail="合并后文件大小不一致")
    return sess
