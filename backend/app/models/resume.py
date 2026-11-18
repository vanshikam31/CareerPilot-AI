from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.user import utcnow


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)  # kept so we can re-embed in Phase 3
    parsed: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(20))  # "gemini" or "fallback"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)