from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.security import api_key_hash, generate_api_key
from app.models.api_key import ApiKey
from app.models.billing import BillingSubscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User, UserRole
from app.schemas.api_key import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyListItem
from app.services.plans import Feature, PLAN_API_KEY_LIMIT, PLAN_FEATURES
from app.services.audit import audit_event

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _current_plan(db: Session, user_id: int) -> SubscriptionPlan:
    sub = (
        db.query(BillingSubscription)
        .filter(BillingSubscription.user_id == user_id)
        .order_by(BillingSubscription.created_at.desc())
        .first()
    )
    if not sub or sub.status != SubscriptionStatus.active:
        return SubscriptionPlan.starter
    return sub.plan


@router.get("", response_model=list[ApiKeyListItem])
def list_keys(db: Session = Depends(get_db), current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager))):
    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


@router.post("", response_model=ApiKeyCreateResponse)
def create_key(
    payload: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    plan = _current_plan(db, current_user.id)
    if Feature.api_access not in PLAN_FEATURES.get(plan, set()):
        raise HTTPException(status_code=403, detail="API access is not enabled for your plan")

    limit = PLAN_API_KEY_LIMIT.get(plan, 0)
    active_count = db.query(ApiKey).filter(ApiKey.user_id == current_user.id, ApiKey.revoked_at.is_(None)).count()
    if active_count >= limit:
        raise HTTPException(status_code=403, detail="API key limit reached for your plan")

    settings = get_settings()
    api_key = generate_api_key(settings.API_KEY_PREFIX)
    prefix = api_key[:12]
    row = ApiKey(
        user_id=current_user.id,
        prefix=prefix,
        key_hash=api_key_hash(api_key, settings.SECRET_KEY),
        name=(payload.name or None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit_event(db, "api_key_create", "api_key", user_id=current_user.id, details=f"key_id={row.id}")
    return ApiKeyCreateResponse(id=row.id, prefix=row.prefix, api_key=api_key)


@router.post("/{key_id}/revoke")
def revoke_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    row = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    row.revoked_at = datetime.utcnow()
    db.commit()
    audit_event(db, "api_key_revoke", "api_key", user_id=current_user.id, details=f"key_id={row.id}")
    return {"status": "revoked"}

