"""Redis 缓存（可选）：环境变量 TENCLIP_CORE_API_REDIS_URL 或 REDIS_URL。"""

from __future__ import annotations

import json
import os
from typing import Any

HOT_NEWS_KEY = "hot_news"
HOT_NEWS_TTL_SEC = 300

_redis_client: Any = None


def _redis_url() -> str:
    return (
        os.environ.get("TENCLIP_CORE_API_REDIS_URL", "").strip()
        or os.environ.get("REDIS_URL", "").strip()
    )


def get_redis():
    """返回已连接的 Redis 客户端；未配置或不可用时返回 None。"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    url = _redis_url()
    if not url:
        return None
    import redis

    r = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    r.ping()
    _redis_client = r
    return r


def hot_news_cache_get() -> dict[str, Any] | None:
    try:
        r = get_redis()
        if r is None:
            return None
        raw = r.get(HOT_NEWS_KEY)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def hot_news_cache_set(payload: dict[str, Any]) -> None:
    try:
        r = get_redis()
        if r is None:
            return
        r.set(HOT_NEWS_KEY, json.dumps(payload, ensure_ascii=False), ex=HOT_NEWS_TTL_SEC)
    except Exception:
        pass


def hot_news_cache_invalidate() -> None:
    try:
        r = get_redis()
        if r is None:
            return
        r.delete(HOT_NEWS_KEY)
    except Exception:
        pass
