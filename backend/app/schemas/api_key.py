from datetime import datetime

from pydantic import BaseModel


class ApiKeyCreateRequest(BaseModel):
    name: str | None = None


class ApiKeyCreateResponse(BaseModel):
    id: int
    prefix: str
    api_key: str


class ApiKeyListItem(BaseModel):
    id: int
    prefix: str
    name: str | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True

