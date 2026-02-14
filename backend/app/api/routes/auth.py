from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    validate_password_strength,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import RefreshTokenRequest, RevokeSessionRequest, TokenResponse, UserCreate, UserResponse
from app.services.audit import audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
@limiter.limit("10/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(status_code=403, detail="Public signup is disabled")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if not validate_password_strength(payload.password):
        raise HTTPException(
            status_code=400,
            detail="Weak password. Use 12+ chars with upper/lowercase, number, and symbol.",
        )

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_event(db, "register", "auth", user_id=user.id, ip_address=request.client.host if request.client else None)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    x_device_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    user = db.query(User).filter(User.email == form_data.username).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=423, detail="Account is temporarily locked")

    if not verify_password(form_data.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            user.failed_login_attempts = 0
        db.commit()
        audit_event(
            db,
            "login_failed",
            "auth",
            user_id=user.id,
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    if not x_device_id or len(x_device_id) < 8:
        raise HTTPException(status_code=400, detail="x-device-id header is required")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    access = create_access_token(str(user.id), x_device_id, user.session_version)
    refresh = create_refresh_token(str(user.id), x_device_id, user.session_version)

    audit_event(db, "login_success", "auth", user_id=user.id, ip_address=request.client.host if request.client else None)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, x_device_id: str | None = Header(default=None), db: Session = Depends(get_db)):
    try:
        claims = decode_token(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if claims.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = claims.get("sub")
    token_device = claims.get("did")
    token_sv = claims.get("sv")
    if not user_id or not token_device or token_sv is None:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    if not x_device_id or x_device_id != token_device:
        raise HTTPException(status_code=401, detail="Device verification failed")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or user.session_version != int(token_sv):
        raise HTTPException(status_code=401, detail="Session invalid")

    access = create_access_token(str(user.id), x_device_id, user.session_version)
    refresh = create_refresh_token(str(user.id), x_device_id, user.session_version)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/revoke")
def revoke_sessions(
    _: RevokeSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.session_version += 1
    db.commit()
    return {"status": "revoked"}