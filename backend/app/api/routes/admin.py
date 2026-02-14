from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.user import User, UserRole
from app.services.audit import audit_event

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.admin))):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value,
            "is_active": u.is_active,
            "failed_login_attempts": u.failed_login_attempts,
            "locked_until": u.locked_until.isoformat() if u.locked_until else None,
            "created_at": u.created_at.isoformat(),
        }
        for u in rows
    ]


@router.post("/users/{user_id}/disable")
def disable_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(require_roles(UserRole.admin))):
    if current.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    user.session_version += 1
    db.commit()
    audit_event(db, "admin_user_disable", "admin", user_id=current.id, details=f"target_user_id={user_id}")
    return {"status": "disabled"}

