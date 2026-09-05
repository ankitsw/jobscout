from datetime import datetime, timezone
from sqlalchemy import Text, DateTime, Float, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.services.database import Base


class Company(Base):
    """Cached research for a company, keyed by a normalized name so repeat
    lookups (the same company appears across many job postings) reuse one
    row instead of re-querying search/LLM APIs every time."""

    __tablename__ = "companies"
    __table_args__ = (
        Index("company_lookup_key_unique_idx", "lookup_key", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    lookup_key: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    size: Mapped[str] = mapped_column(Text, default="")
    founded: Mapped[str] = mapped_column(Text, default="")
    headquarters: Mapped[str] = mapped_column(Text, default="")
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    tech_stack: Mapped[list[str]] = mapped_column(JSONB, default=list)
    culture_signals: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="web_search")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
