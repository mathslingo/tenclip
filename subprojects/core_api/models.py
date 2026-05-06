"""子项目 ORM 模型：News / Match / Video / Player（表名加 api_ 前缀，避免与现有 SQLite 表冲突）。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class News(Base):
    __tablename__ = "api_news"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class Match(Base):
    __tablename__ = "api_matches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    home_side: Mapped[str | None] = mapped_column(String(128), nullable=True)
    away_side: Mapped[str | None] = mapped_column(String(128), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(256), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    videos: Mapped[list["Video"]] = relationship(back_populates="match")


class Player(Base):
    __tablename__ = "api_players"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ranking_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    videos: Mapped[list["Video"]] = relationship(back_populates="primary_player")


class Video(Base):
    __tablename__ = "api_videos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    storage_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("api_matches.id", ondelete="SET NULL"), nullable=True
    )
    primary_player_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("api_players.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    match: Mapped["Match | None"] = relationship(back_populates="videos")
    primary_player: Mapped["Player | None"] = relationship(back_populates="videos")
