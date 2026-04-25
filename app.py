import logging
import os
import queue
import shutil
import sqlite3
import threading
import tempfile
import time
import uuid
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# 仓库在 ~/code/tenclip 等任意路径时：若存在本地权重目录，优先直接推理（不再走远程下载）
_REPO_ROOT = Path(__file__).resolve().parent
_LOCAL_VLM = _REPO_ROOT / "model" / "Qwen2-VL-2B-Instruct"
if not os.environ.get("TENCLIP_VLM_MODEL", "").strip() and _LOCAL_VLM.is_dir():
    os.environ["TENCLIP_VLM_MODEL"] = str(_LOCAL_VLM)

import gradio as gr
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from moviepy.video.io.VideoFileClip import VideoFileClip

from pages.video_input.gradio_page import video_input_demo

from services.vlm_tennis import (
    MAX_VIDEO_DURATION_SEC,
    analyze_tennis_video,
    format_guidance_markdown,
    prompt_profile_radio_choices,
    resolve_prompt_profile,
    vlm_dependency_message,
)
from services.news_feed import (
    RecommendInput,
    ingest_news,
    init_news_db,
    record_feedback,
    recommend_news,
    set_user_profile,
    suggest_tags,
)

logging.basicConfig(level=logging.INFO)
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

PERF_MAP = {
    "省显存（弱显卡推荐）": "eco",
    "平衡": "balanced",
    "质量优先（显存充足）": "quality",
}

MOBILE_EVENTS = [
    {
        "id": "evt-101",
        "title": "午间小团课【正手进阶】1号+2号场",
        "timeText": "明天(周三)下午12点 · 1.5小时",
        "locationText": "闵行区吴中路485号古北 · 室内 · 6.4km",
        "joined": 1,
        "capacity": 5,
        "levelMin": 1.0,
        "levelMax": 5.0,
        "playType": "不限",
        "distanceKm": 6.4,
        "startTimestamp": 1765560000,
        "hotScore": 98,
    },
    {
        "id": "evt-102",
        "title": "晨间2小时畅打【4号场】",
        "timeText": "明天(周三)上午8点 · 2小时",
        "locationText": "闵行区吴中路485号古北 · 室内 · 6.4km",
        "joined": 1,
        "capacity": 2,
        "levelMin": 1.0,
        "levelMax": 5.0,
        "playType": "不限",
        "distanceKm": 6.4,
        "startTimestamp": 1765545600,
        "hotScore": 88,
    },
    {
        "id": "evt-103",
        "title": "周日晚 OMC 5.0 双打比赛局",
        "timeText": "本周日晚上8点 · 2小时",
        "locationText": "徐汇区天钥桥路 · 室内 · 4.0km",
        "joined": 2,
        "capacity": 16,
        "levelMin": 2.0,
        "levelMax": 3.0,
        "playType": "双打",
        "distanceKm": 4.0,
        "startTimestamp": 1765800000,
        "hotScore": 76,
    },
]

ANALYSIS_TASKS: dict[str, dict] = {}
ANALYSIS_TASKS_LOCK = threading.Lock()
ANALYSIS_QUEUE: "queue.Queue[tuple[str, str, str, str | None]]" = queue.Queue()
ANALYSIS_WORKER_STARTED = False
ANALYSIS_WORKER_LOCK = threading.Lock()
ANALYSIS_DB = _REPO_ROOT / "data" / "analysis_tasks.db"
UPLOAD_DIR = _REPO_ROOT / "data" / "uploads"

ANALYSIS_RETENTION_PRUNER_STARTED = False
ANALYSIS_RETENTION_PRUNER_LOCK = threading.Lock()


def _video_retention_days() -> int:
    raw = os.environ.get("TENCLIP_VIDEO_RETENTION_DAYS", "60").strip()
    try:
        days = int(raw)
    except ValueError:
        days = 60
    return max(1, min(days, 3650))


def _new_task(task_id: str, perf_mode: str, prompt_profile: str | None) -> dict:
    return {
        "task_id": task_id,
        "status": "queued",  # queued | running | succeeded | failed
        "perf_mode": perf_mode,
        "prompt_profile": prompt_profile or "",
        "prompt_profile_effective": "",
        "guidance": "",
        "error": "",
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
    }


def _db_conn() -> sqlite3.Connection:
    ANALYSIS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ANALYSIS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_analysis_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with _db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                perf_mode TEXT NOT NULL,
                prompt_profile TEXT,
                prompt_profile_effective TEXT,
                guidance TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_videos (
                task_id TEXT PRIMARY KEY,
                original_filename TEXT,
                stored_path TEXT NOT NULL,
                file_size INTEGER NOT NULL DEFAULT 0,
                content_type TEXT,
                uploaded_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'stored'
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_videos_uploaded_at ON analysis_videos(uploaded_at)"
        )
        conn.commit()


def _db_upsert_task(task: dict) -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO analysis_tasks (
                task_id, status, perf_mode, prompt_profile, prompt_profile_effective,
                guidance, error, created_at, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                status=excluded.status,
                perf_mode=excluded.perf_mode,
                prompt_profile=excluded.prompt_profile,
                prompt_profile_effective=excluded.prompt_profile_effective,
                guidance=excluded.guidance,
                error=excluded.error,
                created_at=excluded.created_at,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at
            """,
            (
                task["task_id"],
                task["status"],
                task["perf_mode"],
                task.get("prompt_profile", ""),
                task.get("prompt_profile_effective", ""),
                task.get("guidance", ""),
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
            INSERT OR REPLACE INTO analysis_videos (
                task_id, original_filename, stored_path, file_size, content_type, uploaded_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                original_filename,
                stored_path,
                int(file_size),
                content_type,
                time.time(),
                "stored",
            ),
        )
        conn.commit()


def _db_update_video_status(task_id: str, status: str) -> None:
    with _db_conn() as conn:
        conn.execute("UPDATE analysis_videos SET status=? WHERE task_id=?", (status, task_id))
        conn.commit()


def _db_get_task(task_id: str) -> dict | None:
    with _db_conn() as conn:
        row = conn.execute("SELECT * FROM analysis_tasks WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def _db_list_recent_tasks(limit: int) -> list[dict]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                t.task_id,
                t.status,
                t.perf_mode,
                t.prompt_profile,
                t.prompt_profile_effective,
                t.guidance,
                t.error,
                t.created_at,
                t.started_at,
                t.finished_at,
                v.stored_path,
                v.original_filename,
                v.file_size,
                v.content_type,
                v.uploaded_at AS video_uploaded_at,
                v.status AS video_status
            FROM analysis_tasks t
            LEFT JOIN analysis_videos v ON v.task_id = t.task_id
            ORDER BY t.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def prune_expired_uploads() -> dict[str, int | float]:
    """Remove on-disk uploads older than retention; mark analysis_videos as expired."""
    days = _video_retention_days()
    cutoff = time.time() - days * 86400.0
    removed_files = 0
    marked = 0
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT v.task_id, v.stored_path
            FROM analysis_videos v
            LEFT JOIN analysis_tasks t ON t.task_id = v.task_id
            WHERE v.uploaded_at < ?
              AND v.status <> 'expired'
              AND COALESCE(t.status, '') NOT IN ('queued', 'running')
            """,
            (cutoff,),
        ).fetchall()
        for row in rows:
            p = Path(row["stored_path"])
            if p.is_file():
                try:
                    p.unlink()
                    removed_files += 1
                except OSError:
                    logging.exception("prune unlink failed %s", p)
            conn.execute(
                "UPDATE analysis_videos SET status=? WHERE task_id=?",
                ("expired", row["task_id"]),
            )
            marked += 1
        conn.commit()
    return {
        "retention_days": days,
        "cutoff_timestamp": cutoff,
        "candidates": len(rows),
        "rows_marked_expired": marked,
        "files_removed": removed_files,
    }


def _retention_pruner_loop() -> None:
    logging.info("upload retention pruner started (days=%s)", _video_retention_days())
    while True:
        try:
            summary = prune_expired_uploads()
            if summary["files_removed"] or summary["rows_marked_expired"]:
                logging.info("upload retention prune: %s", summary)
        except Exception:
            logging.exception("upload retention prune failed")
        time.sleep(6 * 3600)


def _ensure_retention_pruner_started() -> None:
    global ANALYSIS_RETENTION_PRUNER_STARTED
    with ANALYSIS_RETENTION_PRUNER_LOCK:
        if ANALYSIS_RETENTION_PRUNER_STARTED:
            return
        t = threading.Thread(target=_retention_pruner_loop, name="upload-retention", daemon=True)
        t.start()
        ANALYSIS_RETENTION_PRUNER_STARTED = True


def _set_task_fields(task_id: str, **fields) -> None:
    task_snapshot = None
    with ANALYSIS_TASKS_LOCK:
        task = ANALYSIS_TASKS.get(task_id)
        if not task:
            return
        task.update(fields)
        task_snapshot = dict(task)
    if task_snapshot:
        _db_upsert_task(task_snapshot)


def _analysis_worker_loop() -> None:
    logging.info("analysis worker started")
    while True:
        task_id, video_path, perf_mode, prompt_profile = ANALYSIS_QUEUE.get()
        _set_task_fields(task_id, status="running", started_at=time.time())
        _db_update_video_status(task_id, "running")
        try:
            guidance = run_mobile_api_analysis(
                video_path=video_path,
                perf_mode=perf_mode,
                prompt_profile=prompt_profile,
            )
            _set_task_fields(
                task_id,
                status="succeeded",
                guidance=guidance,
                prompt_profile_effective=resolve_prompt_profile(prompt_profile),
                finished_at=time.time(),
            )
            _db_update_video_status(task_id, "analyzed")
        except Exception as exc:
            _set_task_fields(
                task_id,
                status="failed",
                error=str(exc),
                finished_at=time.time(),
            )
            _db_update_video_status(task_id, "failed")
        finally:
            ANALYSIS_QUEUE.task_done()


def _ensure_analysis_worker_started() -> None:
    global ANALYSIS_WORKER_STARTED
    with ANALYSIS_WORKER_LOCK:
        if ANALYSIS_WORKER_STARTED:
            return
        t = threading.Thread(target=_analysis_worker_loop, name="analysis-worker", daemon=True)
        t.start()
        ANALYSIS_WORKER_STARTED = True


def _extract_video_path(video_file):
    """Support Gradio file values across versions."""
    if video_file is None:
        return None
    if isinstance(video_file, str):
        return video_file
    if isinstance(video_file, dict):
        return video_file.get("path")
    if hasattr(video_file, "name"):
        return video_file.name
    return None


def trim_video(video_file, start_time, end_time):
    clip = None
    subclip = None
    try:
        video_path = _extract_video_path(video_file)
        if not video_path:
            raise ValueError("请先上传视频文件")
        if not os.path.exists(video_path):
            raise ValueError(f"视频文件不存在: {video_path}")

        start_time = float(start_time)
        end_time = float(end_time)

        clip = VideoFileClip(video_path)
        start_time = max(0, start_time)
        end_time = min(end_time, clip.duration)
        if end_time <= start_time:
            raise ValueError("结束时间必须大于开始时间")

        if hasattr(clip, "subclipped"):
            subclip = clip.subclipped(start_time, end_time)
        else:
            subclip = clip.subclip(start_time, end_time)

        output_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        subclip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        return output_path
    except Exception as e:
        raise gr.Error(f"剪辑失败: {str(e)}")
    finally:
        if subclip is not None:
            subclip.close()
        if clip is not None:
            clip.close()


def run_tennis_analysis(video_file, perf_label, prompt_profile, progress=gr.Progress()):
    path = _extract_video_path(video_file)
    if not path:
        return "请先上传视频文件。"
    hint = vlm_dependency_message()
    if hint:
        return hint
    mode = PERF_MAP.get(perf_label, "eco")
    pp = (prompt_profile or "").strip() or None
    progress(0.05, desc="检查视频与依赖…")
    progress(0.15, desc="抽帧 / 加载模型（首次会下载权重，请耐心等待）…")
    out = analyze_tennis_video(path, mode, prompt_profile=pp)
    progress(1.0, desc="完成")
    return format_guidance_markdown(out)


def run_mobile_api_analysis(video_path: str, perf_mode: str, prompt_profile: str | None = None) -> str:
    hint = vlm_dependency_message()
    if hint:
        raise ValueError(hint)
    pp = (prompt_profile or "").strip() or None
    return analyze_tennis_video(video_path, perf_mode, prompt_profile=pp)


def _vlm_tab_intro():
    dep = vlm_dependency_message()
    base = (
        f"使用 **Qwen2-VL-2B-Instruct**（约 2B）对视频均匀抽帧做视觉理解，"
        f"输出动作是否大致合理及初学者的改进建议。\n\n"
        f"- **推理框架**：优先 **LLaMA-Factory** `ChatModel`（`TENCLIP_INFER_BACKEND=auto`），失败时回退 **Transformers**。\n"
        "- **权重下载**：默认 **ModelScope**（`TENCLIP_MODEL_DOWNLOAD_SOURCE=modelscope`）；HF 不可用时不必改镜像。\n"
        f"- **时长**：仅分析前 **{int(MAX_VIDEO_DURATION_SEC)} 秒**（约 5 分钟）；更长请先剪辑。\n"
        "- **省显存 / 平衡 / 质量**：帧数与分辨率递增，弱显卡请保持「省显存」。\n"
        "- 首次分析前建议运行 `download-vlm-conda.bat` 预下载权重。\n"
    )
    if dep:
        return (
            base
            + "\n**当前环境未安装分析依赖。** Conda：`setup-conda-env.bat`；或 pip："
            + "`pip install -r requirements-llm.txt -r requirements-llm-lf.txt`。\n"
        )
    return base + "\n依赖已就绪，可直接点击「开始分析」。\n"


TENNIS_GUIDANCE_CSS = """
#tennis-guidance {
  font-size: 0.95rem;
  line-height: 1.55;
  color: #1a1f26;
  text-align: left;
}
#tennis-guidance h2 { margin: 0 0 0.5em; font-size: 1.12rem; color: #0d3d32; border-bottom: 1px solid #e5ebe9; padding-bottom: 0.35em; }
#tennis-guidance h3, #tennis-guidance h4 { margin: 0.85em 0 0.35em; font-size: 1.02rem; color: #243240; }
#tennis-guidance p { margin: 0.45em 0; }
#tennis-guidance ul, #tennis-guidance ol { margin: 0.35em 0 0.55em; padding-left: 1.35em; }
#tennis-guidance li { margin: 0.22em 0; }
#tennis-guidance pre {
  background: #f4f6f9;
  border: 1px solid #e5e9f0;
  border-radius: 10px;
  padding: 10px 12px;
  overflow-x: auto;
  font-size: 0.8rem;
  line-height: 1.45;
}
#tennis-guidance details { margin-top: 1rem; border-radius: 12px; border: 1px solid #e5e9f0; padding: 8px 10px; background: #fafbfc; }
#tennis-guidance summary { cursor: pointer; font-size: 0.9rem; color: #415360; }
#tennis-guidance hr { border: 0; border-top: 1px solid #e8ecf1; margin: 1em 0; }
#tennis-guidance code { background: #eef2f6; padding: 0.12em 0.35em; border-radius: 4px; font-size: 0.88em; }
"""


with gr.Blocks(title="TenClip", css=TENNIS_GUIDANCE_CSS) as demo:
    gr.Markdown("# TenClip：网球视频剪辑与动作分析")

    with gr.Tabs():
        with gr.Tab("视频剪辑"):
            gr.Markdown("上传视频，按秒裁剪并下载片段。")
            with gr.Row():
                trim_file = gr.File(label="上传视频 (MP4/MOV/AVI)", file_types=[".mp4", ".mov", ".avi"])
                t_start = gr.Number(label="开始时间（秒）", value=0)
                t_end = gr.Number(label="结束时间（秒）", value=10)
            trim_btn = gr.Button("剪辑并下载", variant="primary")
            trim_out = gr.File(label="剪辑结果")

            trim_btn.click(trim_video, inputs=[trim_file, t_start, t_end], outputs=trim_out)

        with gr.Tab("网球动作分析（大模型）"):
            gr.Markdown(_vlm_tab_intro())
            with gr.Row():
                tennis_file = gr.File(label="上传网球视频", file_types=[".mp4", ".mov", ".avi"])
                perf = gr.Radio(
                    list(PERF_MAP.keys()),
                    value="省显存（弱显卡推荐）",
                    label="显存 / 质量模式",
                )
            prompt_prof = gr.Radio(
                choices=prompt_profile_radio_choices(),
                value="default",
                label="分析提示词版本",
            )
            tennis_btn = gr.Button("开始分析", variant="primary")
            tennis_out = gr.Markdown(
                elem_id="tennis-guidance",
            )

            tennis_btn.click(
                run_tennis_analysis,
                inputs=[tennis_file, perf, prompt_prof],
                outputs=tennis_out,
            )

            gr.Markdown(
                "**弱显卡建议**：保持「省显存」；若仍 OOM，可先剪辑更短片段，"
                "或在启动前设置环境变量 `TENCLIP_FORCE_CPU=1` 强制走 CPU（会慢很多）。"
            )


def create_app() -> FastAPI:
    api = FastAPI(title="TenClip API")
    init_news_db()
    init_analysis_db()
    _ensure_analysis_worker_started()
    try:
        prune_expired_uploads()
    except Exception:
        logging.exception("initial upload retention prune failed")
    _ensure_retention_pruner_started()

    # 主 Gradio 若挂在 path="/"，会注册 Mount("/") 抢走所有子路径（含 /video_input），故主界面改挂 /gradio。
    @api.get("/", include_in_schema=False)
    def root_to_gradio():
        return RedirectResponse(url="/gradio/", status_code=302)

    @api.get("/api/mobile/events")
    def mobile_events():
        return {"events": MOBILE_EVENTS}

    @api.post("/api/mobile/analyze-video")
    async def mobile_analyze_video(
        video: UploadFile = File(...),
        perf_mode: str = Form("eco"),
        prompt_profile: str = Form(""),
    ):
        suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
        temp_path = Path(tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name)
        try:
            with temp_path.open("wb") as out_file:
                shutil.copyfileobj(video.file, out_file)
            pp = prompt_profile.strip() or None
            guidance = run_mobile_api_analysis(
                str(temp_path), perf_mode=perf_mode, prompt_profile=pp
            )
            return {
                "guidance": guidance,
                "perf_mode": perf_mode,
                "prompt_profile": resolve_prompt_profile(pp),
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"分析失败: {exc}") from exc
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                logging.exception("Failed to cleanup temp file: %s", temp_path)
            await video.close()

    @api.post("/api/mobile/analyze-video/submit")
    async def mobile_analyze_video_submit(
        video: UploadFile = File(...),
        perf_mode: str = Form("eco"),
        prompt_profile: str = Form(""),
    ):
        task_id = uuid.uuid4().hex
        suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
        upload_path = UPLOAD_DIR / f"{task_id}{suffix}"
        try:
            with upload_path.open("wb") as out_file:
                shutil.copyfileobj(video.file, out_file)

            pp = prompt_profile.strip() or None
            task = _new_task(task_id, perf_mode=perf_mode, prompt_profile=pp)
            with ANALYSIS_TASKS_LOCK:
                ANALYSIS_TASKS[task_id] = task
            _db_upsert_task(task)
            _db_insert_video(
                task_id=task_id,
                original_filename=video.filename or "",
                stored_path=str(upload_path),
                file_size=upload_path.stat().st_size if upload_path.exists() else 0,
                content_type=video.content_type or "",
            )
            ANALYSIS_QUEUE.put((task_id, str(upload_path), perf_mode, pp))
            return {
                "task_id": task_id,
                "status": "queued",
                "queue_size": ANALYSIS_QUEUE.qsize(),
                "stored_path": str(upload_path),
            }
        except Exception as exc:
            try:
                upload_path.unlink(missing_ok=True)
            except Exception:
                logging.exception("Failed to cleanup submit temp file: %s", upload_path)
            raise HTTPException(status_code=500, detail=f"提交失败: {exc}") from exc
        finally:
            await video.close()

    @api.get("/api/mobile/analyze-video/tasks")
    def mobile_analyze_video_tasks_list(limit: int = Query(50, ge=1, le=200)):
        items = _db_list_recent_tasks(limit)
        for row in items:
            row["queue_size"] = ANALYSIS_QUEUE.qsize()
        return {"items": items, "retention_days": _video_retention_days()}

    @api.get("/api/mobile/analyze-video/tasks/{task_id}")
    def mobile_analyze_video_task_status(task_id: str):
        with ANALYSIS_TASKS_LOCK:
            task = ANALYSIS_TASKS.get(task_id)
            data = dict(task) if task else None
        if data is None:
            data = _db_get_task(task_id)
        if data is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        data["queue_size"] = ANALYSIS_QUEUE.qsize()
        return data

    @api.post("/api/mobile/analyze-video/tasks/prune")
    def mobile_analyze_video_tasks_prune():
        return prune_expired_uploads()

    @api.post("/api/news/ingest")
    def news_ingest(limit_per_source: int = Query(20, ge=1, le=100)):
        result = ingest_news(limit_per_source=limit_per_source)
        return {"ok": True, **result}

    @api.get("/api/news/tags")
    def news_tags(limit: int = Query(40, ge=1, le=200)):
        return {"tags": suggest_tags(limit=limit)}

    @api.post("/api/news/profile")
    def news_profile(user_id: str = Form(...), tags: str = Form("")):
        tag_list = [x.strip() for x in tags.split(",") if x.strip()]
        set_user_profile(user_id=user_id, tags=tag_list)
        return {"ok": True, "user_id": user_id, "tags": tag_list}

    @api.post("/api/news/feedback")
    def news_feedback(
        user_id: str = Form(...),
        article_id: int = Form(...),
        action: str = Form(...),
    ):
        record_feedback(user_id=user_id, article_id=article_id, action=action)
        return {"ok": True}

    @api.get("/api/news/feed")
    def news_feed(
        user_id: str = Query("", description="匿名用户可留空"),
        tags: str = Query("", description="逗号分隔 tag"),
        limit: int = Query(20, ge=1, le=60),
        offset: int = Query(0, ge=0),
    ):
        tag_list = [x.strip() for x in tags.split(",") if x.strip()]
        items = recommend_news(
            RecommendInput(
                user_tags=tag_list,
                limit=limit,
                offset=offset,
                user_id=user_id.strip() or None,
            )
        )
        return {"items": items, "next_offset": offset + len(items)}

    front_page_dir = _REPO_ROOT / "pages" / "front_page"
    if front_page_dir.exists():
        # 独立 Web 入口（响应式：PC/手机皆可）；静态资源走独立前缀，避免与 Gradio 根路由冲突。
        api.mount("/web-assets", StaticFiles(directory=str(front_page_dir)), name="web-assets")

        @api.get("/web")
        @api.get("/web/")
        def web_home():
            return FileResponse(front_page_dir / "index.html")

        # 兼容旧地址：/mobile -> /web
        @api.get("/mobile")
        @api.get("/mobile/")
        def mobile_home():
            return FileResponse(front_page_dir / "index.html")

    news_page_dir = _REPO_ROOT / "pages" / "news_page"
    if news_page_dir.exists():
        api.mount("/news-assets", StaticFiles(directory=str(news_page_dir)), name="news-assets")

        @api.get("/news")
        @api.get("/news/")
        def news_home():
            return FileResponse(news_page_dir / "index.html")

    # 简单 H5（Gradio）：上传视频 + 指导意见，风格贴近 front_page（须在主界面 /gradio 之前注册，避免被吞）
    gr.mount_gradio_app(api, video_input_demo, path="/video_input")

    return gr.mount_gradio_app(api, demo, path="/gradio")


def main() -> None:
    port = int(os.environ.get("GRADIO_SERVER_PORT", "7861"))
    host = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
