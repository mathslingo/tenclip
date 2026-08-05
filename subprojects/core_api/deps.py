"""FastAPI 依赖：从请求头解析 JWT 并加载当前用户。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .db import get_db
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Session = Depends(get_db),
) -> models.User:
    """
    从 ``Authorization: Bearer <JWT>`` 提取 token，校验后返回 ``User``。
    任一环节失败返回 401。
    """
    _www = {"WWW-Authenticate": "Bearer"}
    if creds is None or creds.scheme.lower() != "bearer" or not (creds.credentials or "").strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers=_www,
        )
    user_id = decode_access_token(creds.credentials.strip())
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers=_www,
        )
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found",
            headers=_www,
        )
    return user
