import hmac
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{12,128}$")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> bool:
    return bool(PASSWORD_RE.match(password))


def _token_payload(subject: str, token_type: str, device_id: str, session_version: int) -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return {
        "sub": subject,
        "typ": token_type,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "jti": secrets.token_urlsafe(24),
        "did": device_id,
        "sv": session_version,
    }


def create_access_token(subject: str, device_id: str, session_version: int, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = _token_payload(subject, "access", device_id, session_version)
    payload["exp"] = expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ZERO_TRUST_SIGNING_ALG)


def create_refresh_token(subject: str, device_id: str, session_version: int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = _token_payload(subject, "refresh", device_id, session_version)
    payload["exp"] = expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ZERO_TRUST_SIGNING_ALG)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ZERO_TRUST_SIGNING_ALG],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )


def verify_webhook_signature(secret: str, timestamp: str, body: bytes, signature: str, max_skew_seconds: int) -> bool:
    if not secret:
        return False

    try:
        ts = int(timestamp)
    except Exception:
        return False

    now = int(datetime.now(timezone.utc).timestamp())
    if abs(now - ts) > max_skew_seconds:
        return False

    signed_payload = f"{timestamp}.".encode("utf-8") + body
    computed = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def generate_device_id() -> str:
    return secrets.token_urlsafe(16)


def api_key_hash(api_key: str, secret: str) -> str:
    # Stable HMAC hash for API keys; store only this.
    return hmac.new(secret.encode("utf-8"), api_key.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_api_key(prefix: str) -> str:
    # Prefix is helpful for identification; the secret portion is random.
    return f"{prefix}{secrets.token_urlsafe(32)}"
