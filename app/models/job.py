from sqlalchemy import Text, DateTime, Boolean, Index, Computed
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from pgvector.sqlalchemy import Vector
from app.services.database import Base

class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("job_url_unique_idx", "url", unique=True),
        Index("job_fts_index", "fts", postgresql_using="gin")
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    experience_required: Mapped[str] = mapped_column()
    location: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    easy_apply: Mapped[bool] = mapped_column(Boolean, default=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    emailed: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    #full-text-search
    fts: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))", persisted=True),
        nullable=True
    ) 