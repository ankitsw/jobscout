from datetime import datetime, timezone
from sqlalchemy import Text, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.services.database import Base

class GeneratedCv(Base):
    __tablename__ = "generated_cvs"
    __table_args__ = (
        # One saved CV per resume+job pair - regenerating overwrites it
        # rather than piling up duplicates.
        Index("generated_cv_resume_job_unique_idx", "resume_id", "job_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resume_id: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
