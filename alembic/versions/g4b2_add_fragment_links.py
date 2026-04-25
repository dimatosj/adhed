"""add fragment_links table

Revision ID: g4b2
Revises: f3a1
Create Date: 2026-04-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'g4b2'
down_revision: Union[str, Sequence[str], None] = 'f3a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fragment_links',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('fragment_id', UUID(as_uuid=True), sa.ForeignKey('fragments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('target_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('fragment_id', 'target_type', 'target_id', name='uq_fragment_link'),
    )
    op.create_index('ix_fragment_links_target', 'fragment_links', ['target_type', 'target_id'])


def downgrade() -> None:
    op.drop_index('ix_fragment_links_target', table_name='fragment_links')
    op.drop_table('fragment_links')
