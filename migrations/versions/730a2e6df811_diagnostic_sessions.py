"""Store diagnostic sessions and the results of their checks."""

import sqlalchemy as sa
from alembic import op

revision = "730a2e6df811"
down_revision = "5f0b2f6d9a31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chat_id", sa.Integer(), sa.ForeignKey("chats.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("bench", sa.String(120), nullable=False),
        sa.Column("environment", sa.String(200), nullable=False),
        sa.Column("steps", sa.Text(), nullable=False),
        sa.Column("expected", sa.Text(), nullable=False),
        sa.Column("observed", sa.Text(), nullable=False),
        sa.Column("log_name", sa.String(255), nullable=True),
        sa.Column("log_excerpt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "request_id"),
        sa.UniqueConstraint("chat_id"),
        sa.CheckConstraint("status IN ('open', 'resolved')"),
    )
    op.create_index(
        "ix_diagnostic_sessions_user_id", "diagnostic_sessions", ["user_id"]
    )
    op.create_table(
        "diagnostic_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("diagnostic_sessions.id"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("session_id", "request_id"),
        sa.CheckConstraint("outcome IN ('passed', 'failed', 'inconclusive')"),
        sa.CheckConstraint("source IN ('manual', 'stand', 'ci')"),
    )
    op.create_index(
        "ix_diagnostic_checks_session_id", "diagnostic_checks", ["session_id"]
    )


def downgrade():
    op.drop_table("diagnostic_checks")
    op.drop_table("diagnostic_sessions")
