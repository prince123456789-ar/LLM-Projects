from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def audit_event(db: Session, action: str, resource: str, user_id: int | None = None, ip_address: str | None = None, details: str | None = None) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        ip_address=ip_address,
        details=details,
    )
    db.add(entry)
    db.commit()
