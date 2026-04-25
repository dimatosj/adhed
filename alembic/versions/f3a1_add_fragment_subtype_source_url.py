"""add subtype and source_url to fragments

Revision ID: f3a1
Revises: e11e4eab41d7
Create Date: 2026-04-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f3a1'
down_revision: Union[str, Sequence[str], None] = 'e11e4eab41d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fragments', sa.Column('subtype', sa.Text(), nullable=True))
    op.add_column('fragments', sa.Column('source_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('fragments', 'source_url')
    op.drop_column('fragments', 'subtype')
