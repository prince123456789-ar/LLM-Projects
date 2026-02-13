from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.report import ReportFrequency


class ScheduledReportCreate(BaseModel):
    frequency: ReportFrequency
    recipient_email: EmailStr
    report_type: str = "analytics"


class ScheduledReportResponse(BaseModel):
    id: int
    frequency: ReportFrequency
    recipient_email: EmailStr
    report_type: str
    created_by_user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
