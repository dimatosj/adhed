"""Add custom_fields JSONB to projects."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "m9g7"
down_revision = "k8f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("custom_fields", JSONB(), nullable=True))
    op.create_index(
        "ix_projects_custom_fields", "projects", ["custom_fields"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_projects_custom_fields", table_name="projects", postgresql_using="gin")
    op.drop_column("projects", "custom_fields")
