"""Store the names and analysis excerpts of chat attachments."""

import sqlalchemy as sa
from alembic import op

revision = "5f0b2f6d9a31"
down_revision = "4c3d8b917ac0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("attachment_name", sa.String(255)))
    op.add_column("messages", sa.Column("attachment_excerpt", sa.Text()))


def downgrade():
    op.drop_column("messages", "attachment_excerpt")
    op.drop_column("messages", "attachment_name")
