import secrets
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)
analytics_key_scheme = APIKeyHeader(name="X-Analytics-Key", auto_error=False)


def _user_from_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not active")
    return user


def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    token = credentials.credentials if credentials else request.cookies.get("okdriver_token")
    return _user_from_token(token, db)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = _user_from_token(credentials.credentials if credentials else request.cookies.get("okdriver_token"), db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def get_event_actor(
    api_key: str | None = Depends(analytics_key_scheme),
    user: User | None = Depends(get_optional_current_user),
) -> User | None:
    if api_key is not None:
        if not settings.analytics_api_key or not secrets.compare_digest(api_key, settings.analytics_api_key):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid analytics API key")
        return None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_roles(*roles: str) -> Callable:
    async def role_dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return role_dependency


def get_websocket_token(websocket) -> str | None:
    token = websocket.cookies.get("okdriver_token")
    if token:
        return token
    header = websocket.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value
    return websocket.query_params.get("token")
