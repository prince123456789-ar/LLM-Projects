from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LeadChannel(str, enum.Enum):
    whatsapp = "whatsapp"
    instagram = "instagram"
    facebook = "facebook"
    website_chat = "website_chat"
    email = "email"


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    converted = "converted"
    lost = "lost"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(30), index=True)
    channel: Mapped[LeadChannel] = mapped_column(Enum(LeadChannel), nullable=False)
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.new, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    property_type: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(120))
    budget: Mapped[float | None] = mapped_column(Float)
    timeline: Mapped[str | None] = mapped_column(String(80))
    assigned_agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    embedding: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    assigned_agent = relationship("User")
