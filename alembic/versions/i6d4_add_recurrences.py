"""add recurrences table

Revision ID: i6d4
Revises: g4b2
Create Date: 2026-05-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = 'i6d4'
down_revision: Union[str, Sequence[str], None] = 'g4b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recurrences',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('team_id', UUID(as_uuid=True), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title_template', sa.String(500), nullable=False),
        sa.Column('description_template', sa.Text(), nullable=True),
        sa.Column('issue_defaults', JSONB, nullable=True),
        sa.Column('schedule_type', sa.String(20), nullable=False),
        sa.Column('schedule_expr', sa.String(100), nullable=False),
        sa.Column('next_due_at', sa.DateTime(), nullable=False),
        sa.Column('last_spawned_at', sa.DateTime(), nullable=True),
        sa.Column('last_spawned_issue_id', UUID(as_uuid=True), sa.ForeignKey('issues.id'), nullable=True),
        sa.Column('active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_recurrences_team', 'recurrences', ['team_id'])
    op.create_index('ix_recurrences_due', 'recurrences', ['active', 'next_due_at'])


def downgrade() -> None:
    op.drop_index('ix_recurrences_due', table_name='recurrences')
    op.drop_index('ix_recurrences_team', table_name='recurrences')
    op.drop_table('recurrences')
