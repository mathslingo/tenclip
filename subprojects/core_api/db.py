"""数据库引擎与会话（独立 SQLite，不影响 news_feed / analysis_tasks）。"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _default_sqlite_url() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    db_path = repo_root / "data" / "core_api.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL = os.environ.get("TENCLIP_CORE_API_DATABASE_URL", "").strip() or _default_sqlite_url()

connect_args = {}
if DATABASE_URL.startswith("sqlite:"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def migrate_sqlite_api_news_detail_columns() -> None:
    """为已有 SQLite 库补齐新闻详情字段（create_all 不会改已存在表结构）。"""
    if not DATABASE_URL.startswith("sqlite:"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(api_news)")).fetchall()
        if not rows:
            return
        names = {row[1] for row in rows}
        if "body" not in names:
            conn.execute(text("ALTER TABLE api_news ADD COLUMN body TEXT"))
        if "tags" not in names:
            conn.execute(text("ALTER TABLE api_news ADD COLUMN tags VARCHAR(1024)"))
        if "players" not in names:
            conn.execute(text("ALTER TABLE api_news ADD COLUMN players VARCHAR(1024)"))


def migrate_sqlite_api_matches_columns() -> None:
    """为已有 SQLite 库的 api_matches 补齐与 ORM 一致的列（create_all 不会改已存在表结构）。"""
    if not DATABASE_URL.startswith("sqlite:"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(api_matches)")).fetchall()
        if not rows:
            return
        names = {row[1] for row in rows}
        # (列名, ALTER 语句)；仅添加缺失列，类型与 models.Match 对齐
        statements: list[tuple[str, str]] = [
            ("name", "ALTER TABLE api_matches ADD COLUMN name VARCHAR(256)"),
            ("tournament", "ALTER TABLE api_matches ADD COLUMN tournament VARCHAR(256)"),
            ("event_round", "ALTER TABLE api_matches ADD COLUMN event_round VARCHAR(128)"),
            ("home_side", "ALTER TABLE api_matches ADD COLUMN home_side VARCHAR(128)"),
            ("away_side", "ALTER TABLE api_matches ADD COLUMN away_side VARCHAR(128)"),
            ("player1_id", "ALTER TABLE api_matches ADD COLUMN player1_id CHAR(32)"),
            ("player2_id", "ALTER TABLE api_matches ADD COLUMN player2_id CHAR(32)"),
            ("score", "ALTER TABLE api_matches ADD COLUMN score VARCHAR(256)"),
            ("venue", "ALTER TABLE api_matches ADD COLUMN venue VARCHAR(256)"),
            ("scheduled_at", "ALTER TABLE api_matches ADD COLUMN scheduled_at DATETIME"),
            (
                "status",
                "ALTER TABLE api_matches ADD COLUMN status VARCHAR(64) NOT NULL DEFAULT 'scheduled'",
            ),
            (
                "created_at",
                "ALTER TABLE api_matches ADD COLUMN created_at DATETIME NOT NULL "
                "DEFAULT (datetime('now'))",
            ),
        ]
        for col, stmt in statements:
            if col not in names:
                conn.execute(text(stmt))


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
