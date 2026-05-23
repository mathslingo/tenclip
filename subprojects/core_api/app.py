"""
独立 FastAPI 应用入口（未接入根 `app.py`）。

运行示例（仓库根目录、已安装 requirements-subproject-core-api.txt）：

    uvicorn subprojects.core_api.app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import and_, false, func, select
from sqlalchemy.orm import Session

from . import models
from .xhs_note_routes import register_xhs_note_routes
from .xhs_preview import register_xhs_preview_routes
from .db import (
    Base,
    engine,
    get_db,
    migrate_sqlite_api_matches_columns,
    migrate_sqlite_api_news_detail_columns,
)
from .deps import get_current_user
from .redis_cache import hot_news_cache_get, hot_news_cache_invalidate, hot_news_cache_set
from .security import create_access_token, hash_password, verify_password

HOT_NEWS_CACHE_ITEM_CAP = 200

_log = logging.getLogger("uvicorn.error")


class NewsBase(BaseModel):
    title: str
    summary: str | None = None
    body: str | None = None
    tags: str | None = Field(None, description="逗号或中文逗号分隔的标签")
    players: str | None = Field(None, description="逗号或中文逗号分隔的球员名")
    source_url: str | None = None
    published_at: datetime | None = None


class NewsCreate(NewsBase):
    pass


class NewsUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    source_url: str | None = None
    published_at: datetime | None = None


class NewsRead(NewsBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class PlayerBase(BaseModel):
    display_name: str
    country_code: str | None = None
    ranking_points: float | None = None


class PlayerCreate(PlayerBase):
    pass


class PlayerUpdate(BaseModel):
    display_name: str | None = None
    country_code: str | None = None
    ranking_points: float | None = None


class PlayerRead(PlayerBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class MatchBase(BaseModel):
    name: str | None = None
    tournament: str | None = None
    event_round: str | None = None
    home_side: str | None = None
    away_side: str | None = None
    player1_id: UUID | None = None
    player2_id: UUID | None = None
    score: str | None = None
    venue: str | None = None
    scheduled_at: datetime | None = None
    status: str = "scheduled"


class MatchCreate(MatchBase):
    pass


class MatchUpdate(BaseModel):
    name: str | None = None
    tournament: str | None = None
    event_round: str | None = None
    home_side: str | None = None
    away_side: str | None = None
    player1_id: UUID | None = None
    player2_id: UUID | None = None
    score: str | None = None
    venue: str | None = None
    scheduled_at: datetime | None = None
    status: str | None = None


class MatchRead(MatchBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class VideoBase(BaseModel):
    title: str | None = None
    storage_uri: str
    duration_sec: int | None = None
    match_id: UUID | None = None
    primary_player_id: UUID | None = None


class VideoCreate(VideoBase):
    pass


class VideoUpdate(BaseModel):
    title: str | None = None
    storage_uri: str | None = None
    duration_sec: int | None = None
    match_id: UUID | None = None
    primary_player_id: UUID | None = None


class VideoRead(VideoBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int


class NewsListResponse(BaseModel):
    items: list[NewsRead]
    pagination: PaginationMeta


class PlayerListResponse(BaseModel):
    items: list[PlayerRead]
    pagination: PaginationMeta


class MatchListResponse(BaseModel):
    items: list[MatchRead]
    pagination: PaginationMeta


class VideoListResponse(BaseModel):
    items: list[VideoRead]
    pagination: PaginationMeta


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    created_at: datetime


def _get_or_404(db: Session, model_cls: Any, item_id: UUID, resource_name: str):
    obj = db.get(model_cls, item_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")
    return obj


def _error_payload(code: str, message: str, detail: Any = None):
    return {"ok": False, "error": {"code": code, "message": message, "detail": detail}}


def _hot_news_cache_payload(db: Session) -> dict[str, Any]:
    total = db.scalar(select(func.count()).select_from(models.News)) or 0
    stmt = (
        select(models.News)
        .order_by(
            func.coalesce(models.News.published_at, models.News.created_at).desc(),
            models.News.created_at.desc(),
        )
        .limit(HOT_NEWS_CACHE_ITEM_CAP)
    )
    rows = list(db.scalars(stmt))
    items = [NewsRead.model_validate(r).model_dump(mode="json") for r in rows]
    return {
        "items": items,
        "pagination": {"page": 1, "page_size": HOT_NEWS_CACHE_ITEM_CAP, "total": total},
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_sqlite_api_news_detail_columns()
    migrate_sqlite_api_matches_columns()
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="TenClip Core API", lifespan=lifespan)

    @application.middleware("http")
    async def json_error_middleware(request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=_error_payload("HTTP_ERROR", str(exc.detail), exc.detail),
            )
        except Exception as exc:
            _log.error("unhandled exception on %s %s\n%s", request.method, request.url.path, traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content=_error_payload("INTERNAL_ERROR", "internal server error", str(exc)),
            )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_payload("VALIDATION_ERROR", "request validation failed", exc.errors()),
        )

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload("HTTP_ERROR", str(exc.detail), exc.detail),
        )

    @application.get("/")
    def root():
        return {
            "name": "TenClip Core API",
            "status": "ok",
            "endpoints": ["/health", "/auth/register", "/auth/login", "/auth/me"],
        }

    @application.get("/health")
    def health():
        return {"status": "ok"}

    @application.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
    def auth_register(payload: UserRegister, db: Session = Depends(get_db)):
        exists = db.scalar(select(models.User).where(models.User.email == payload.email.lower()))
        if exists:
            raise HTTPException(status_code=409, detail="email already registered")
        user = models.User(
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @application.post("/auth/login", response_model=TokenResponse)
    def auth_login(payload: UserLogin, db: Session = Depends(get_db)):
        user = db.scalar(select(models.User).where(models.User.email == payload.email.lower()))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid email or password")
        token = create_access_token(user_id=user.id)
        return TokenResponse(access_token=token)

    @application.get("/auth/me", response_model=UserRead)
    def auth_me(user: models.User = Depends(get_current_user)):
        return user

    @application.get("/news", response_model=NewsListResponse)
    def list_news(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=200),
        date_from: datetime | None = Query(None),
        date_to: datetime | None = Query(None),
        tournament: str | None = Query(None, description="按赛事关键字筛选（title/summary 模糊匹配）"),
        player_id: UUID | None = Query(
            None,
            description="按球员：新闻 title/summary/body/tags/players 字段中含该球员 display_name",
        ),
        db: Session = Depends(get_db),
    ):
        filters: list[Any] = []
        if date_from is not None:
            filters.append(models.News.published_at >= date_from)
        if date_to is not None:
            filters.append(models.News.published_at <= date_to)
        if tournament:
            like = f"%{tournament}%"
            filters.append(
                models.News.title.ilike(like) | models.News.summary.ilike(like)  # type: ignore[arg-type]
            )
        if player_id is not None:
            pobj = db.get(models.Player, player_id)
            if pobj is None:
                raise HTTPException(status_code=404, detail="player not found")
            nm = (pobj.display_name or "").strip()
            if nm:
                like = f"%{nm}%"
                filters.append(
                    models.News.title.ilike(like)
                    | models.News.summary.ilike(like)  # type: ignore[arg-type]
                    | models.News.body.ilike(like)  # type: ignore[arg-type]
                    | models.News.tags.ilike(like)  # type: ignore[arg-type]
                    | models.News.players.ilike(like)  # type: ignore[arg-type]
                )
            else:
                filters.append(false())

        stmt = select(models.News)
        if filters:
            stmt = stmt.where(and_(*filters))
        count_stmt = select(func.count(models.News.id)).select_from(models.News)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = int(db.scalar(count_stmt) or 0)
        offset = (page - 1) * page_size
        items = list(
            db.scalars(stmt.order_by(models.News.created_at.desc()).offset(offset).limit(page_size))
        )
        return {"items": items, "pagination": {"page": page, "page_size": page_size, "total": total}}

    @application.post("/news", response_model=NewsRead, status_code=status.HTTP_201_CREATED)
    def create_news(payload: NewsCreate, db: Session = Depends(get_db)):
        item = models.News(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @application.get("/news/{news_id}", response_model=NewsRead)
    def get_news(news_id: UUID, db: Session = Depends(get_db)):
        return _get_or_404(db, models.News, news_id, "news")

    @application.put("/news/{news_id}", response_model=NewsRead)
    def update_news(news_id: UUID, payload: NewsUpdate, db: Session = Depends(get_db)):
        item = _get_or_404(db, models.News, news_id, "news")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(item, k, v)
        db.commit()
        db.refresh(item)
        hot_news_cache_invalidate()
        return item

    @application.delete("/news/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_news(news_id: UUID, db: Session = Depends(get_db)):
        item = _get_or_404(db, models.News, news_id, "news")
        db.delete(item)
        db.commit()
        hot_news_cache_invalidate()

    @application.get("/players", response_model=PlayerListResponse)
    def list_players(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=200),
        date_from: datetime | None = Query(None),
        date_to: datetime | None = Query(None),
        db: Session = Depends(get_db),
    ):
        stmt = select(models.Player)
        if date_from is not None:
            stmt = stmt.where(models.Player.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(models.Player.created_at <= date_to)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        offset = (page - 1) * page_size
        items = list(
            db.scalars(stmt.order_by(models.Player.created_at.desc()).offset(offset).limit(page_size))
        )
        return {"items": items, "pagination": {"page": page, "page_size": page_size, "total": total}}

    @application.post("/players", response_model=PlayerRead, status_code=status.HTTP_201_CREATED)
    def create_player(payload: PlayerCreate, db: Session = Depends(get_db)):
        item = models.Player(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @application.get("/players/{player_id}", response_model=PlayerRead)
    def get_player(player_id: UUID, db: Session = Depends(get_db)):
        return _get_or_404(db, models.Player, player_id, "player")

    @application.put("/players/{player_id}", response_model=PlayerRead)
    def update_player(player_id: UUID, payload: PlayerUpdate, db: Session = Depends(get_db)):
        item = _get_or_404(db, models.Player, player_id, "player")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(item, k, v)
        db.commit()
        db.refresh(item)
        return item

    @application.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_player(player_id: UUID, db: Session = Depends(get_db)):
        item = _get_or_404(db, models.Player, player_id, "player")
        db.delete(item)
        db.commit()

    @application.get("/matches", response_model=MatchListResponse)
    def list_matches(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=200),
        date_from: datetime | None = Query(None, description="按 scheduled_at 起始时间"),
        date_to: datetime | None = Query(None, description="按 scheduled_at 结束时间"),
        tournament: str | None = Query(None, description="赛事名模糊匹配"),
        player_id: UUID | None = Query(None, description="任一侧为该球员（player1_id 或 player2_id）"),
        db: Session = Depends(get_db),
    ):
        filters = []
        if date_from is not None:
            filters.append(models.Match.scheduled_at >= date_from)
        if date_to is not None:
            filters.append(models.Match.scheduled_at <= date_to)
        if tournament:
            filters.append(models.Match.tournament.ilike(f"%{tournament}%"))
        if player_id is not None:
            filters.append(
                (models.Match.player1_id == player_id) | (models.Match.player2_id == player_id)
            )

        stmt = select(models.Match)
        if filters:
            stmt = stmt.where(and_(*filters))

        count_stmt = select(func.count(models.Match.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = int(db.scalar(count_stmt) or 0)

        offset = (page - 1) * page_size
        items = list(
            db.scalars(stmt.order_by(models.Match.created_at.desc()).offset(offset).limit(page_size))
        )
        return {"items": items, "pagination": {"page": page, "page_size": page_size, "total": total}}

    @application.post("/matches", response_model=MatchRead, status_code=status.HTTP_201_CREATED)
    def create_match(payload: MatchCreate, db: Session = Depends(get_db)):
        item = models.Match(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @application.get("/matches/{match_id}", response_model=MatchRead)
    def get_match(match_id: UUID, db: Session = Depends(get_db)):
        return _get_or_404(db, models.Match, match_id, "match")

    @application.put("/matches/{match_id}", response_model=MatchRead)
    def update_match(match_id: UUID, payload: MatchUpdate, db: Session = Depends(get_db)):
        item = _get_or_404(db, models.Match, match_id, "match")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(item, k, v)
        db.commit()
        db.refresh(item)
        return item

    @application.delete("/matches/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_match(match_id: UUID, db: Session = Depends(get_db)):
        item = _get_or_404(db, models.Match, match_id, "match")
        db.delete(item)
        db.commit()

    @application.get("/videos", response_model=VideoListResponse)
    def list_videos(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=200),
        date_from: datetime | None = Query(None, description="按视频 created_at 起始时间"),
        date_to: datetime | None = Query(None, description="按视频 created_at 结束时间"),
        tournament: str | None = Query(None, description="按关联 Match.tournament 模糊匹配"),
        match_id: UUID | None = Query(None, description="按比赛 ID 精确筛选（集锦列表）"),
        db: Session = Depends(get_db),
    ):
        filters: list[Any] = []
        if match_id is not None:
            filters.append(models.Video.match_id == match_id)
        if date_from is not None:
            filters.append(models.Video.created_at >= date_from)
        if date_to is not None:
            filters.append(models.Video.created_at <= date_to)
        if tournament:
            filters.append(models.Match.tournament.ilike(f"%{tournament}%"))

        stmt = select(models.Video)
        if tournament:
            stmt = stmt.join(models.Match, models.Video.match_id == models.Match.id)
        if filters:
            stmt = stmt.where(and_(*filters))

        count_stmt = select(func.count(models.Video.id)).select_from(models.Video)
        if tournament:
            count_stmt = count_stmt.join(models.Match, models.Video.match_id == models.Match.id)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = int(db.scalar(count_stmt) or 0)

        offset = (page - 1) * page_size
        items = list(
            db.scalars(
                stmt.order_by(models.Video.created_at.desc()).offset(offset).limit(page_size)
            )
        )
        return {"items": items, "pagination": {"page": page, "page_size": page_size, "total": total}}

    @application.post("/videos", response_model=VideoRead, status_code=status.HTTP_201_CREATED)
    def create_video(payload: VideoCreate, db: Session = Depends(get_db)):
        item = models.Video(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @application.get("/videos/{video_id}", response_model=VideoRead)
    def get_video(video_id: UUID, db: Session = Depends(get_db)):
        return _get_or_404(db, models.Video, video_id, "video")

    @application.put("/videos/{video_id}", response_model=VideoRead)
    def update_video(video_id: UUID, payload: VideoUpdate, db: Session = Depends(get_db)):
        item = _get_or_404(db, models.Video, video_id, "video")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(item, k, v)
        db.commit()
        db.refresh(item)
        return item

    @application.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_video(video_id: UUID, db: Session = Depends(get_db)):
        item = _get_or_404(db, models.Video, video_id, "video")
        db.delete(item)
        db.commit()

    register_xhs_preview_routes(application)
    register_xhs_note_routes(application)

    return application


app = create_app()
