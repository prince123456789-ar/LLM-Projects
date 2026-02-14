from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    # Display prefix only (safe to store and show in UI).
    prefix: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    # HMAC-SHA256 over the full API key (never store plaintext).
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    name: Mapped[str | None] = mapped_column(String(120))

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

