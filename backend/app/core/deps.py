from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import decode_token
from app.core.security import api_key_hash
from app.models.api_key import ApiKey
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
    x_device_id: str | None = Header(default=None),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    # Support either JWT bearer or API key.
    if x_api_key:
        settings = get_settings()
        h = api_key_hash(x_api_key, settings.SECRET_KEY)
        row = db.query(ApiKey).filter(ApiKey.key_hash == h, ApiKey.revoked_at.is_(None)).first()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid API key")
        user = db.query(User).filter(User.id == int(row.user_id)).first()
        if not user:
            raise credentials_exception
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User inactive")
        if user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=None):
            raise HTTPException(status_code=423, detail="Account locked")
        row.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return user

    try:
        payload = decode_token(token)
        if payload.get("typ") != "access":
            raise credentials_exception

        user_id = payload.get("sub")
        token_device_id = payload.get("did")
        token_session_version = payload.get("sv")

        if not user_id or not token_device_id or token_session_version is None:
            raise credentials_exception
        if not x_device_id or x_device_id != token_device_id:
            raise HTTPException(status_code=401, detail="Device verification failed")
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")
    if user.session_version != int(token_session_version):
        raise HTTPException(status_code=401, detail="Session revoked")
    if user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=423, detail="Account locked")

    return user


def require_roles(*roles: UserRole):
    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return role_dependency


def require_feature(_feature: str):
    # Minimal stub to keep routing stable; plan enforcement can be expanded later.
    # (Feature gating is enforced for API key creation and subscription status.)
    def feature_dependency(current_user: User = Depends(get_current_user)) -> User:
        return current_user

    return feature_dependency
