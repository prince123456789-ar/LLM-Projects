from datetime import datetime, timedelta, timezone

import base64
import hashlib
import hmac
import secrets
from urllib.parse import urlencode

import requests

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
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
from app.models.user import UserRole
from app.schemas.auth import MeResponse, RefreshTokenRequest, RevokeSessionRequest, TokenResponse, UserCreate, UserResponse
from app.services.audit import audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
@limiter.limit("10/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(status_code=403, detail="Public signup is disabled")

    # Least privilege: public signup creates a manager account (billing/analytics enabled),
    # and can never create admin accounts.
    if payload.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin accounts must be created by backend bootstrap")

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
        role=UserRole.manager,
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


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/google/login")
def google_login(request: Request):
    """Start Google OAuth login (no extra dependencies)."""
    settings = get_settings()
    if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET or not settings.GOOGLE_OAUTH_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    state = secrets.token_urlsafe(24)
    mac = hmac.new(settings.SECRET_KEY.encode("utf-8"), state.encode("utf-8"), hashlib.sha256).digest()
    signed = state + "." + base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")

    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    resp = RedirectResponse(url=url)
    resp.set_cookie("oauth_state", signed, httponly=True, samesite="lax", secure=False, max_age=600)
    return resp


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET or not settings.GOOGLE_OAUTH_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    cookie = request.cookies.get("oauth_state") or ""
    if not code or not state or "." not in cookie:
        raise HTTPException(status_code=400, detail="Google login failed")

    st, sig = cookie.split(".", 1)
    mac = hmac.new(settings.SECRET_KEY.encode("utf-8"), st.encode("utf-8"), hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")
    if not hmac.compare_digest(sig, expected) or st != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if token_res.status_code >= 400:
        raise HTTPException(status_code=400, detail="Google token exchange failed")
    token_json = token_res.json()
    access_token = token_json.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google token exchange failed")

    ui_res = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if ui_res.status_code >= 400:
        raise HTTPException(status_code=400, detail="Google userinfo failed")
    userinfo = ui_res.json()
    email = userinfo.get("email")
    name = userinfo.get("name") or "Google User"
    if not email:
        raise HTTPException(status_code=400, detail="Google login failed")

    # Auto-provision user (manager role) if public signup allowed; otherwise require existing account.
    existing = db.query(User).filter(User.email == email).first()
    if not existing:
        if not settings.ALLOW_PUBLIC_SIGNUP:
            raise HTTPException(status_code=403, detail="Account not found")
        existing = User(
            full_name=name,
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            role=UserRole.manager,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

    # Create tokens and pass them via URL fragment (not sent to server) for the UI to store.
    device_id = secrets.token_hex(16)
    access = create_access_token(str(existing.id), device_id, existing.session_version)
    refresh = create_refresh_token(str(existing.id), device_id, existing.session_version)
    url = f"{settings.FRONTEND_URL}/app/login#access_token={access}&refresh_token={refresh}&device_id={device_id}&next=/app/dashboard"
    resp = RedirectResponse(url=url)
    resp.delete_cookie("oauth_state")
    return resp
