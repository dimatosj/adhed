"""Add note to FragmentType enum."""

from alembic import op

revision = "k8f6"
down_revision = "j7e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE fragmenttype ADD VALUE IF NOT EXISTS 'NOTE'")


def downgrade() -> None:
    pass
