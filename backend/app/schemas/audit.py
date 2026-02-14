from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    action: str
    resource: str
    ip_address: str | None
    details: str | None
    created_at: datetime

