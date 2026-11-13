"""Replace Azure-specific columns with GitHub Actions identities.

Revision ID: 4c3d8b917ac0
Revises: 689ab6c61c4a
"""

import sqlalchemy as sa
from alembic import op

revision = "4c3d8b917ac0"
down_revision = "689ab6c61c4a"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("pipelines_azure_pipeline_id_check", "pipelines", type_="check")
    op.alter_column(
        "pipelines",
        "azure_pipeline_id",
        new_column_name="workflow_file",
        type_=sa.String(255),
        postgresql_using="azure_pipeline_id::text",
    )
    op.alter_column(
        "runs", "azure_run_id", new_column_name="external_run_id", type_=sa.BigInteger()
    )
    op.add_column("runs", sa.Column("request_id", sa.String(36), nullable=True))
    op.create_unique_constraint("uq_runs_request_id", "runs", ["request_id"])
    op.alter_column("jobs", "azure_job_id", new_column_name="external_job_id")
    op.alter_column(
        "jobs", "azure_log_id", new_column_name="external_log_id", type_=sa.BigInteger()
    )
    op.alter_column(
        "artifacts", "azure_artifact_name", new_column_name="external_artifact_id"
    )


def downgrade():
    # Do not silently destroy GitHub workflow identities during rollback.
    count = (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM pipelines WHERE workflow_file !~ '^[0-9]+$'")
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            "GitHub pipelines exist; export/remove them before downgrade"
        )
    op.alter_column(
        "artifacts", "external_artifact_id", new_column_name="azure_artifact_name"
    )
    op.alter_column(
        "jobs", "external_log_id", new_column_name="azure_log_id", type_=sa.Integer()
    )
    op.alter_column("jobs", "external_job_id", new_column_name="azure_job_id")
    op.drop_constraint("uq_runs_request_id", "runs", type_="unique")
    op.drop_column("runs", "request_id")
    op.alter_column(
        "runs", "external_run_id", new_column_name="azure_run_id", type_=sa.Integer()
    )
    op.alter_column(
        "pipelines",
        "workflow_file",
        new_column_name="azure_pipeline_id",
        type_=sa.Integer(),
        postgresql_using="workflow_file::integer",
    )
    op.create_check_constraint(
        "pipelines_azure_pipeline_id_check", "pipelines", "azure_pipeline_id > 0"
    )
