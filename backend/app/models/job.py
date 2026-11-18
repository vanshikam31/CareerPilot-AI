from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import EMBED_DIM
from app.database.session import Base
from app.models.user import utcnow


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("title", "company", "location", name="uq_job_title_company_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    company: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(100), index=True)
    work_mode: Mapped[str] = mapped_column(String(20), index=True)  # onsite | hybrid | remote
    experience_level: Mapped[str] = mapped_column(String(20), index=True)  # fresher | junior | mid | senior
    category: Mapped[str] = mapped_column(String(50))
    skills: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text)
    # Real pgvector column on PostgreSQL; a JSON list on SQLite so unit tests run without Docker.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBED_DIM).with_variant(JSON(), "sqlite"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)