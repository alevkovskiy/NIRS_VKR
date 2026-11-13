from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.enums import RunStatus


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_runs_user_request"),
        CheckConstraint(
            "status IN ('pending', 'submission_unknown', 'submission_failed', "
            "'queued', "
            "'in_progress', 'completed')"
        ),
        CheckConstraint(
            "result IS NULL OR result IN "
            "('succeeded', 'partially_succeeded', 'failed', 'canceled')"
        ),
        CheckConstraint("result IS NULL OR status = 'completed'"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    external_run_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    request_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    submission_error: Mapped[str | None] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(200))
    branch: Mapped[str] = mapped_column(String(255))
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.PENDING.value)
    result: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
