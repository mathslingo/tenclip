"""击球片段提取异步任务（供小程序 / H5 上传轮询）。"""

from __future__ import annotations

import json
import logging
import os
import queue
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from services.stroke_detect import StrokeDetectConfig, run_stroke_extract_pipeline

_REPO_ROOT = Path(__file__).resolve().parent.parent
STROKE_DB = _REPO_ROOT / "data" / "stroke_extract_tasks.db"
STROKE_UPLOAD_DIR = _REPO_ROOT / "data" / "uploads" / "stroke"
STROKE_OUTPUT_DIR = _REPO_ROOT / "data" / "stroke_outputs"

STROKE_TASKS: dict[str, dict[str, Any]] = {}
STROKE_TASKS_LOCK = threading.Lock()
STROKE_QUEUE: queue.Queue[tuple[str, str, str, float, bool]] = queue.Queue()
STROKE_WORKER_STARTED = False
STROKE_WORKER_LOCK = threading.Lock()


def _new_stroke_task(
    task_id: str,
    *,
    detect_mode: str,
    motion_percentile: float,
    vlm_filter: bool,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "queued",
        "detect_mode": detect_mode,
        "motion_percentile": motion_percentile,
        "vlm_filter": vlm_filter,
        "progress_message": "",
        "progress_frac": 0.0,
        "summary": "",
        "result": None,
        "output_path": "",
        "error": "",
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
    }


def _db_conn() -> sqlite3.Connection:
    STROKE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STROKE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_stroke_db() -> None:
    STROKE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    STROKE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with _db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stroke_extract_tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                detect_mode TEXT NOT NULL,
                motion_percentile REAL NOT NULL,
                vlm_filter INTEGER NOT NULL DEFAULT 0,
                progress_message TEXT,
                progress_frac REAL NOT NULL DEFAULT 0,
                summary TEXT,
                result_json TEXT,
                output_path TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stroke_extract_videos (
                task_id TEXT PRIMARY KEY,
                original_filename TEXT,
                stored_path TEXT NOT NULL,
                file_size INTEGER NOT NULL DEFAULT 0,
                content_type TEXT,
                uploaded_at REAL NOT NULL
            )
            """
        )
        conn.commit()


def _db_upsert_task(task: dict[str, Any]) -> None:
    result_json = ""
    if task.get("result") is not None:
        result_json = json.dumps(task["result"], ensure_ascii=False)
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO stroke_extract_tasks (
                task_id, status, detect_mode, motion_percentile, vlm_filter,
                progress_message, progress_frac, summary, result_json, output_path,
                error, created_at, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                status=excluded.status,
                progress_message=excluded.progress_message,
                progress_frac=excluded.progress_frac,
                summary=excluded.summary,
                result_json=excluded.result_json,
                output_path=excluded.output_path,
                error=excluded.error,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at
            """,
            (
                task["task_id"],
                task["status"],
                task["detect_mode"],
                float(task["motion_percentile"]),
                1 if task.get("vlm_filter") else 0,
                task.get("progress_message", ""),
                float(task.get("progress_frac") or 0.0),
                task.get("summary", ""),
                result_json,
                task.get("output_path", ""),
                task.get("error", ""),
                task["created_at"],
                task.get("started_at"),
                task.get("finished_at"),
            ),
        )
        conn.commit()


def _db_insert_video(
    task_id: str,
    original_filename: str,
    stored_path: str,
    file_size: int,
    content_type: str,
) -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO stroke_extract_videos (
                task_id, original_filename, stored_path, file_size, content_type, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                original_filename,
                stored_path,
                int(file_size),
                content_type,
                time.time(),
            ),
        )
        conn.commit()


def _db_get_task(task_id: str) -> dict[str, Any] | None:
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM stroke_extract_tasks WHERE task_id=?", (task_id,)
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    raw = data.pop("result_json", "") or ""
    data["result"] = json.loads(raw) if raw else None
    data["vlm_filter"] = bool(data.get("vlm_filter"))
    return data


def _set_stroke_task_fields(task_id: str, **fields: Any) -> None:
    task_snapshot = None
    with STROKE_TASKS_LOCK:
        task = STROKE_TASKS.get(task_id)
        if not task:
            return
        task.update(fields)
        task_snapshot = dict(task)
    if task_snapshot:
        _db_upsert_task(task_snapshot)


def format_stroke_summary(result_dict: dict[str, Any], *, vlm_filter: bool) -> str:
    duration = float(result_dict.get("duration_sec") or 0)
    kept = float(result_dict.get("kept_sec") or 0)
    ratio = float(result_dict.get("kept_ratio") or 0)
    segments = result_dict.get("segments") or []
    mode = result_dict.get("mode") or "combined"
    lines = [
        f"原时长 {duration:.1f}s → 保留 {kept:.1f}s（{ratio:.0%}）",
        f"片段数 {len(segments)} · 模式 {mode}"
        + (" · VLM 过滤已启用" if vlm_filter else ""),
    ]
    for i, seg in enumerate(segments[:12]):
        lines.append(
            f"{i + 1}. {seg.get('start', 0):.1f}s – {seg.get('end', 0):.1f}s"
            f"（{seg.get('duration', 0):.1f}s）"
        )
    if len(segments) > 12:
        lines.append(f"… 共 {len(segments)} 段")
    return "\n".join(lines)


def _stroke_worker_loop() -> None:
    logging.info("stroke extract worker started")
    while True:
        task_id, video_path, detect_mode, motion_percentile, vlm_filter = STROKE_QUEUE.get()
        _set_stroke_task_fields(task_id, status="running", started_at=time.time())

        output_path = STROKE_OUTPUT_DIR / f"{task_id}.mp4"

        def _prog(msg: str, frac: float) -> None:
            _set_stroke_task_fields(
                task_id,
                progress_message=msg,
                progress_frac=round(min(0.99, max(0.0, frac)), 3),
            )

        try:
            if vlm_filter:
                from services.vlm_tennis import vlm_dependency_message

                hint = vlm_dependency_message()
                if hint:
                    raise ValueError(f"VLM 不可用：{hint}")

            cfg = StrokeDetectConfig(motion_percentile=float(motion_percentile))
            _prog("开始分析（长视频流式处理）…", 0.02)
            result = run_stroke_extract_pipeline(
                video_path,
                output_path,
                mode=detect_mode,  # type: ignore[arg-type]
                config=cfg,
                vlm_filter=vlm_filter,
                vlm_mode="eco",
                copy=False,
                progress=_prog,
            )
            result_dict = result.to_dict()
            if not result.segments:
                _set_stroke_task_fields(
                    task_id,
                    status="failed",
                    error="未检测到击球/回合片段，可尝试降低运动灵敏度或更换检测模式。",
                    result=result_dict,
                    finished_at=time.time(),
                    progress_frac=1.0,
                )
            else:
                summary = format_stroke_summary(result_dict, vlm_filter=vlm_filter)
                _set_stroke_task_fields(
                    task_id,
                    status="succeeded",
                    summary=summary,
                    result=result_dict,
                    output_path=str(output_path),
                    progress_message="完成",
                    progress_frac=1.0,
                    finished_at=time.time(),
                )
        except Exception as exc:
            logging.exception("stroke task %s failed", task_id)
            _set_stroke_task_fields(
                task_id,
                status="failed",
                error=str(exc),
                finished_at=time.time(),
            )
        finally:
            STROKE_QUEUE.task_done()


def ensure_stroke_worker_started() -> None:
    global STROKE_WORKER_STARTED
    with STROKE_WORKER_LOCK:
        if STROKE_WORKER_STARTED:
            return
        t = threading.Thread(target=_stroke_worker_loop, name="stroke-extract", daemon=True)
        t.start()
        STROKE_WORKER_STARTED = True


def submit_stroke_task(
    *,
    upload_path: Path,
    original_filename: str,
    content_type: str,
    detect_mode: str,
    motion_percentile: float,
    vlm_filter: bool,
    task_id: str | None = None,
) -> dict[str, Any]:
    task_id = task_id or uuid.uuid4().hex
    task = _new_stroke_task(
        task_id,
        detect_mode=detect_mode,
        motion_percentile=motion_percentile,
        vlm_filter=vlm_filter,
    )
    with STROKE_TASKS_LOCK:
        STROKE_TASKS[task_id] = task
    _db_upsert_task(task)
    _db_insert_video(
        task_id=task_id,
        original_filename=original_filename,
        stored_path=str(upload_path),
        file_size=upload_path.stat().st_size if upload_path.exists() else 0,
        content_type=content_type,
    )
    STROKE_QUEUE.put((task_id, str(upload_path), detect_mode, motion_percentile, vlm_filter))
    return {
        "task_id": task_id,
        "status": "queued",
        "queue_size": STROKE_QUEUE.qsize(),
    }


def get_stroke_task(task_id: str) -> dict[str, Any] | None:
    with STROKE_TASKS_LOCK:
        task = STROKE_TASKS.get(task_id)
        data = dict(task) if task else None
    if data is None:
        data = _db_get_task(task_id)
    return data


def get_stroke_output_path(task_id: str) -> Path | None:
    task = get_stroke_task(task_id)
    if not task or task.get("status") != "succeeded":
        return None
    p = Path(task.get("output_path") or "")
    if p.is_file():
        return p
    fallback = STROKE_OUTPUT_DIR / f"{task_id}.mp4"
    return fallback if fallback.is_file() else None
