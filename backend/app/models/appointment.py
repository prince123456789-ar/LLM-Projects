from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppointmentStatus(str, enum.Enum):
    suggested = "suggested"
    confirmed = "confirmed"
    completed = "completed"
    canceled = "canceled"


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    timezone: Mapped[str] = mapped_column(String(60), default="UTC", nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[AppointmentStatus] = mapped_column(Enum(AppointmentStatus), default=AppointmentStatus.suggested, nullable=False)
    external_event_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
