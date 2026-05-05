"""Add position column to issues for ordered subtasks."""

from alembic import op
import sqlalchemy as sa

revision = "i6d4"
down_revision = "h5c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("issues", sa.Column("position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("issues", "position")
