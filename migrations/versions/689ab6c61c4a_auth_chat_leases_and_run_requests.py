"""auth_chat_leases_and_run_requests

Revision ID: 689ab6c61c4a
Revises: 7d0e33e1f243
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "689ab6c61c4a"
down_revision: Union[str, Sequence[str], None] = "7d0e33e1f243"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "access_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_access_sessions_expires_at"),
        "access_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_sessions_user_id"), "access_sessions", ["user_id"], unique=False
    )
    op.add_column(
        "chats", sa.Column("generation_id", sa.String(length=36), nullable=True)
    )
    op.add_column(
        "chats",
        sa.Column("generation_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "runs", sa.Column("idempotency_key", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "runs", sa.Column("submission_error", sa.String(length=500), nullable=True)
    )
    op.create_unique_constraint(
        "uq_runs_user_request", "runs", ["user_id", "idempotency_key"]
    )
    op.drop_constraint("runs_status_check", "runs", type_="check")
    op.create_check_constraint(
        "runs_status_check",
        "runs",
        "status IN ('pending', 'submission_unknown', 'submission_failed', "
        "'queued', 'in_progress', 'completed')",
    )


def downgrade() -> None:
    # Preserve rows when returning to the older state vocabulary.
    op.execute("UPDATE runs SET status = 'pending' WHERE status = 'submission_unknown'")
    op.drop_constraint("runs_status_check", "runs", type_="check")
    op.create_check_constraint(
        "runs_status_check",
        "runs",
        "status IN ('pending', 'submission_failed', 'queued', "
        "'in_progress', 'completed')",
    )
    op.drop_constraint("uq_runs_user_request", "runs", type_="unique")
    op.drop_column("runs", "submission_error")
    op.drop_column("runs", "idempotency_key")
    op.drop_column("chats", "generation_started_at")
    op.drop_column("chats", "generation_id")
    op.drop_index(op.f("ix_access_sessions_user_id"), table_name="access_sessions")
    op.drop_index(op.f("ix_access_sessions_expires_at"), table_name="access_sessions")
    op.drop_table("access_sessions")
