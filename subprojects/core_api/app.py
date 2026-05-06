"""
独立 FastAPI 应用入口（未接入根 `app.py`）。

运行示例（仓库根目录、已安装 requirements-subproject-core-api.txt）：

    uvicorn subprojects.core_api.app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, engine
from . import models as _models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="TenClip Core API", lifespan=lifespan)

    @application.get("/health")
    def health():
        return {"status": "ok"}

    return application


app = create_app()
