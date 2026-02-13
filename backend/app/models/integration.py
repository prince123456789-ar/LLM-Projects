from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.lead import LeadChannel


class IntegrationStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class ChannelIntegration(Base):
    __tablename__ = "channel_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel: Mapped[LeadChannel] = mapped_column(Enum(LeadChannel), nullable=False, unique=True)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(String(500))
    api_key_ref: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[IntegrationStatus] = mapped_column(Enum(IntegrationStatus), default=IntegrationStatus.active)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CalendarIntegration(Base):
    __tablename__ = "calendar_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), default="google", nullable=False)
    refresh_token_ref: Mapped[str | None] = mapped_column(String(255))
    calendar_id: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
