from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmbedKey(Base):
    __tablename__ = "embed_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    # Safe to show in UI.
    prefix: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    # HMAC-SHA256 over the full publishable key (used for lookup).
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    # Encrypted full publishable key (only returned to the owning user).
    token_enc: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional comma-separated allowlist like: "https://example.com,https://www.example.com"
    allowed_origins: Mapped[str | None] = mapped_column(Text)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

