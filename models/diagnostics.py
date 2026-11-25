from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id"),
        CheckConstraint("status IN ('open', 'resolved')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), unique=True)
    request_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), default="open")
    title: Mapped[str] = mapped_column(String(120))
    bench: Mapped[str] = mapped_column(String(120))
    environment: Mapped[str] = mapped_column(String(200))
    steps: Mapped[str] = mapped_column(Text)
    expected: Mapped[str] = mapped_column(Text)
    observed: Mapped[str] = mapped_column(Text)
    log_name: Mapped[str | None] = mapped_column(String(255))
    log_excerpt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DiagnosticCheck(Base):
    __tablename__ = "diagnostic_checks"
    __table_args__ = (
        UniqueConstraint("session_id", "request_id"),
        CheckConstraint("outcome IN ('passed', 'failed', 'inconclusive')"),
        CheckConstraint("source IN ('manual', 'stand', 'ci')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_sessions.id"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    outcome: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
