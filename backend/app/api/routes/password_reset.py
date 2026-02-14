import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import api_key_hash, get_password_hash, validate_password_strength
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.password_reset import ForgotPasswordRequest, ResetPasswordRequest
from app.services.audit import audit_event
from app.services.email import send_email

router = APIRouter(prefix="/password", tags=["password"])


@router.post("/forgot")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    user = db.query(User).filter(User.email == payload.email).first()

    # Always return success to avoid user enumeration.
    if not user:
        return {"status": "ok"}

    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES)
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=api_key_hash(token, settings.SECRET_KEY),
        expires_at=expires.replace(tzinfo=None),
    )
    db.add(row)
    db.commit()

    reset_url = f"{settings.FRONTEND_URL}/app/reset-password?token={token}"
    body = (
        "You requested a password reset.\n\n"
        f"Reset link (expires in {settings.PASSWORD_RESET_TOKEN_TTL_MINUTES} minutes):\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    try:
        send_email(user.email, "Reset your password", body)
    except Exception:
        # Do not leak SMTP details to client.
        audit_event(db, "password_reset_email_failed", "auth", user_id=user.id, details="smtp_error")
        if settings.ENVIRONMENT.lower() != "production":
            # Dev-only: allow testing without SMTP by returning the reset URL.
            return {"status": "ok", "debug_reset_url": reset_url}
        return {"status": "ok"}

    audit_event(db, "password_reset_requested", "auth", user_id=user.id, ip_address=request.client.host if request.client else None)
    if settings.ENVIRONMENT.lower() != "production":
        return {"status": "ok", "debug_reset_url": reset_url}
    return {"status": "ok"}


@router.post("/reset")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not validate_password_strength(payload.new_password):
        raise HTTPException(status_code=400, detail="Weak password. Use 12+ chars with upper/lowercase, number, and symbol.")

    token_h = api_key_hash(payload.token, settings.SECRET_KEY)
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_h).first()
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row.used_at is not None or row.expires_at < now:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == int(row.user_id)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")

    user.hashed_password = get_password_hash(payload.new_password)
    user.session_version += 1  # revoke existing sessions
    row.used_at = now
    db.commit()

    audit_event(db, "password_reset_completed", "auth", user_id=user.id, ip_address=request.client.host if request.client else None)
    return {"status": "ok"}
