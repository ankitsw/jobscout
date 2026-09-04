from datetime import datetime, timezone
from sqlalchemy import Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.services.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    # TODO: auto-incrementing primary key, same pattern as Job and Resume
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # TODO: which conversation this message belongs to (plain string, not a foreign key)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)

    # TODO: who sent it — "user", "assistant", or "summary"
    role: Mapped[str] = mapped_column(Text, nullable=False)

    # TODO: the actual message text
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # TODO: when it was sent — same auto-stamping pattern as Job.created_at
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
