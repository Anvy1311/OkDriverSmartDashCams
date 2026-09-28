from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...dependencies import get_current_user, get_optional_current_user
from ...models import User
from ...schemas import LoginRequest, TokenResponse, UserOut
from ...security import create_access_token, verify_password
from ...services.audit import record_audit

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(
        select(User).where(
            func.lower(User.username) == credentials.username.lower(),
            User.is_active.is_(True),
        )
    )
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_access_token(user.username, user.role)
    max_age = settings.token_ttl_minutes * 60
    response.set_cookie(
        key="okdriver_token",
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    record_audit(
        db, "auth.login", "user", user.id, user.id, {"client": request.client.host if request.client else "unknown"}
    )
    db.commit()
    return TokenResponse(
        access_token=token,
        expires_in=max_age,
        user=UserOut.model_validate(user),
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> dict[str, str]:
    record_audit(
        db,
        "auth.logout",
        "user",
        user.id if user else None,
        user.id if user else None,
        {"client": request.client.host if request.client else "unknown"},
    )
    db.commit()
    response.delete_cookie(key="okdriver_token", path="/")
    return {"message": "Signed out"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
