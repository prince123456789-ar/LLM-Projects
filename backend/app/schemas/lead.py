from datetime import datetime
from pydantic import BaseModel, EmailStr

from app.models.lead import LeadChannel, LeadStatus


class LeadCreate(BaseModel):
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    channel: LeadChannel
    raw_message: str = ""

    # Optional structured fields (UI-friendly). AI can still re-extract from raw_message.
    property_type: str | None = None
    location: str | None = None
    budget: float | None = None
    timeline: str | None = None


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
    assigned_agent_id: int | None = None


class LeadResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr | None
    phone: str | None
    channel: LeadChannel
    raw_message: str
    status: LeadStatus
    score: float
    property_type: str | None
    location: str | None
    budget: float | None
    timeline: str | None
    assigned_agent_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True
