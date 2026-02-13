from datetime import datetime

from pydantic import BaseModel

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    lead_id: int
    agent_id: int
    start_at: datetime
    end_at: datetime
    timezone: str = "UTC"
    location: str | None = None


class AppointmentResponse(BaseModel):
    id: int
    lead_id: int
    agent_id: int
    start_at: datetime
    end_at: datetime
    timezone: str
    location: str | None
    status: AppointmentStatus
    external_event_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus


class TimeSlotSuggestion(BaseModel):
    start_at: datetime
    end_at: datetime
