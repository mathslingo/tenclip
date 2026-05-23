#!/usr/bin/env python3
"""一次性校验 subprojects/core_api：依赖、建表、导入 FastAPI。"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> int:
    try:
        from subprojects.core_api.db import Base, engine
        from subprojects.core_api import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        from sqlalchemy import inspect

        tables = sorted(inspect(engine).get_table_names())
        expected = {"api_matches", "api_news", "api_players", "api_users", "api_videos", "api_xhs_notes"}
        missing = expected - set(tables)
        if missing:
            print("FAIL missing tables:", missing, file=sys.stderr)
            return 1

        from subprojects.core_api.app import create_app
        from starlette.testclient import TestClient

        app = create_app()
        paths = [getattr(r, "path", None) for r in app.routes]
        if "/health" not in paths:
            print("FAIL /health missing:", paths, file=sys.stderr)
            return 1
        route_paths = {p for p in paths if p}
        if "/utils/xhs-note-preview" not in route_paths:
            print("FAIL /utils/xhs-note-preview missing", file=sys.stderr)
            return 1
        if "/utils/xhs-note-previews" not in route_paths:
            print("FAIL /utils/xhs-note-previews missing", file=sys.stderr)
            return 1
        if "/utils/xhs-search-note-ids" not in route_paths:
            print("FAIL /utils/xhs-search-note-ids missing", file=sys.stderr)
            return 1
        if "/utils/xhs-search-previews" not in route_paths:
            print("FAIL /utils/xhs-search-previews missing", file=sys.stderr)
            return 1

        if "/utils/xhs-cached-notes" not in route_paths:
            print("FAIL /utils/xhs-cached-notes missing", file=sys.stderr)
            return 1

        client = TestClient(app)
        resp = client.get("/health")
        if resp.status_code != 200 or resp.json().get("status") != "ok":
            print("FAIL /health response:", resp.status_code, resp.text, file=sys.stderr)
            return 1

        batch_empty = client.post("/utils/xhs-note-previews", json={"note_ids": [], "urls": []})
        if batch_empty.status_code != 400:
            print("FAIL POST empty xhs batch:", batch_empty.status_code, batch_empty.text, file=sys.stderr)
            return 1
        bad_id = client.post("/utils/xhs-note-previews", json={"note_ids": ["not24hex"], "urls": []})
        if bad_id.status_code != 400:
            print("FAIL POST bad xhs note_id:", bad_id.status_code, bad_id.text, file=sys.stderr)
            return 1

        s_kw = client.get("/utils/xhs-search-note-ids")
        if s_kw.status_code != 400:
            print("FAIL GET xhs-search-note-ids without keyword:", s_kw.status_code, s_kw.text, file=sys.stderr)
            return 1

        reg = client.post(
            "/auth/register",
            json={"email": "verify_core_api@example.com", "password": "testpass12"},
        )
        if reg.status_code not in (201, 409):
            print("FAIL /auth/register:", reg.status_code, reg.text, file=sys.stderr)
            return 1
        login = client.post(
            "/auth/login",
            json={"email": "verify_core_api@example.com", "password": "testpass12"},
        )
        if login.status_code != 200 or "access_token" not in login.json():
            print("FAIL /auth/login:", login.status_code, login.text, file=sys.stderr)
            return 1
        token = login.json()["access_token"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        if me.status_code != 200 or me.json().get("email") != "verify_core_api@example.com":
            print("FAIL /auth/me:", me.status_code, me.text, file=sys.stderr)
            return 1

        news_list = client.get("/news?page=1&page_size=5")
        if news_list.status_code != 200:
            print("FAIL /news:", news_list.status_code, news_list.text, file=sys.stderr)
            return 1
        matches_list = client.get("/matches?page=1&page_size=5")
        if matches_list.status_code != 200:
            print("FAIL /matches:", matches_list.status_code, matches_list.text, file=sys.stderr)
            return 1

        print("OK tables:", tables)
        print("OK routes:", paths)
        print("OK GET /health:", resp.json())
        print("OK auth flow")
        print("OK GET /news list")
        print("OK GET /matches list")
        return 0
    except Exception as e:
        print("FAIL", e, file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
