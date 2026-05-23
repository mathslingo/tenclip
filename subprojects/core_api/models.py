"""子项目 ORM 模型：User / News / Match / Video / Player（表名加 api_ 前缀）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "api_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class News(Base):
    __tablename__ = "api_news"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    players: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class Match(Base):
    __tablename__ = "api_matches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tournament: Mapped[str | None] = mapped_column(String(256), nullable=True)
    event_round: Mapped[str | None] = mapped_column(String(128), nullable=True)
    home_side: Mapped[str | None] = mapped_column(String(128), nullable=True)
    away_side: Mapped[str | None] = mapped_column(String(128), nullable=True)
    player1_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("api_players.id", ondelete="SET NULL"), nullable=True
    )
    player2_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("api_players.id", ondelete="SET NULL"), nullable=True
    )
    score: Mapped[str | None] = mapped_column(String(256), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(256), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    videos: Mapped[list["Video"]] = relationship(back_populates="match")
    player1: Mapped["Player | None"] = relationship(
        foreign_keys=[player1_id], back_populates="matches_as_player1"
    )
    player2: Mapped["Player | None"] = relationship(
        foreign_keys=[player2_id], back_populates="matches_as_player2"
    )


class Player(Base):
    __tablename__ = "api_players"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ranking_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    videos: Mapped[list["Video"]] = relationship(back_populates="primary_player")
    matches_as_player1: Mapped[list["Match"]] = relationship(
        foreign_keys="Match.player1_id", back_populates="player1"
    )
    matches_as_player2: Mapped[list["Match"]] = relationship(
        foreign_keys="Match.player2_id", back_populates="player2"
    )


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
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    match: Mapped["Match | None"] = relationship(back_populates="videos")
    primary_player: Mapped["Player | None"] = relationship(back_populates="videos")


class XhsCachedNote(Base):
    """离线抓取并校验后写入的小红书笔记摘要（无 Cookie 场景下供首页等复用）。"""

    __tablename__ = "api_xhs_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    note_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    explore_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
