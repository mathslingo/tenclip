"""
本地 VLM 推理 FastAPI 服务（供其它模块 HTTP 调用）。

运行（仓库根目录）：

    bash scripts/start_vlm_api.sh

或：

    python3 -m uvicorn subprojects.vlm_api.app:app --host 127.0.0.1 --port 7862

环境变量：
  TENCLIP_VLM_API_HOST   默认 127.0.0.1
  TENCLIP_VLM_API_PORT   默认 7862
  TENCLIP_VLM_API_KEY    非空时要求请求头 X-API-Key
  TENCLIP_VLM_API_WORKERS  推理线程池大小，默认 1（GPU 建议 1）
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# 与 app.py 一致：本地权重目录自动注入
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_VLM = _REPO_ROOT / "model" / "Qwen2-VL-2B-Instruct"
if not os.environ.get("TENCLIP_VLM_MODEL", "").strip() and _LOCAL_VLM.is_dir():
    os.environ["TENCLIP_VLM_MODEL"] = str(_LOCAL_VLM)

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from services.vlm_tennis import MAX_VIDEO_DURATION_SEC

from .infer import (
    list_prompt_profiles,
    model_status,
    run_analyze_path,
    run_analyze_upload,
    run_chat,
)
from .schemas import (
    AnalyzeVideoPathRequest,
    AnalyzeVideoResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MetaResponse,
)

_log = logging.getLogger("tenclip.vlm_api")
_executor: ThreadPoolExecutor | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _executor
    workers = int(os.environ.get("TENCLIP_VLM_API_WORKERS", "1"))
    workers = max(1, min(workers, 4))
    _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vlm-api")
    _log.info("VLM API started (workers=%s)", workers)
    yield
    if _executor:
        _executor.shutdown(wait=True)
        _executor = None


def create_app() -> FastAPI:
    application = FastAPI(
        title="TenClip VLM API",
        description="本地 Qwen2-VL 推理服务：网球视频分析、多图对话",
        version="1.0.0",
        lifespan=lifespan,
    )

    def _require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
        expected = os.environ.get("TENCLIP_VLM_API_KEY", "").strip()
        if expected and x_api_key != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

    async def _run_sync(fn, *args, **kwargs):
        if _executor is None:
            raise HTTPException(status_code=503, detail="Service not ready")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))

    @application.get("/health", response_model=HealthResponse)
    @application.get("/v1/health", response_model=HealthResponse)
    async def health():
        st = await _run_sync(model_status)
        return HealthResponse(ok=st["model_ready"], **st)

    @application.get("/v1/meta", response_model=MetaResponse)
    async def meta(_: None = Depends(_require_api_key)):
        return MetaResponse(
            perf_modes=["eco", "balanced", "quality"],
            prompt_profiles=list_prompt_profiles(),
            max_video_duration_sec=float(MAX_VIDEO_DURATION_SEC),
        )

    @application.post("/v1/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, _: None = Depends(_require_api_key)):
        if not body.images_base64:
            raise HTTPException(status_code=400, detail="images_base64 至少一张图片")
        try:
            text = await _run_sync(
                run_chat,
                body.prompt,
                system_prompt=body.system_prompt,
                images_base64=body.images_base64,
                perf_mode=body.perf_mode,
                max_new_tokens=body.max_new_tokens,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return ChatResponse(
            text=text,
            perf_mode=body.perf_mode,
            image_count=len(body.images_base64),
        )

    @application.post("/v1/analyze/video", response_model=AnalyzeVideoResponse)
    async def analyze_video_upload(
        video: UploadFile = File(...),
        perf_mode: str = Form("eco"),
        prompt_profile: str = Form("default"),
        _: None = Depends(_require_api_key),
    ):
        suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
        try:
            data = await video.read()
            guidance = await _run_sync(
                run_analyze_upload,
                data,
                suffix,
                perf_mode,
                prompt_profile.strip() or None,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"分析失败: {exc}") from exc
        finally:
            await video.close()
        pp = prompt_profile.strip() or "default"
        return AnalyzeVideoResponse(guidance=guidance, perf_mode=perf_mode, prompt_profile=pp)

    @application.post("/v1/analyze/video/path", response_model=AnalyzeVideoResponse)
    async def analyze_video_path(body: AnalyzeVideoPathRequest, _: None = Depends(_require_api_key)):
        try:
            guidance, pp = await _run_sync(
                run_analyze_path,
                body.video_path,
                body.perf_mode,
                body.prompt_profile,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"分析失败: {exc}") from exc
        return AnalyzeVideoResponse(
            guidance=guidance,
            perf_mode=body.perf_mode,
            prompt_profile=pp,
        )

    @application.get("/", include_in_schema=False)
    async def root():
        return JSONResponse(
            {
                "service": "tenclip-vlm-api",
                "docs": "/docs",
                "health": "/v1/health",
            }
        )

    return application


app = create_app()
