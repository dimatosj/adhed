"""add sessions table and triage_context to issues

Revision ID: h5c3
Revises: g4b2
Create Date: 2026-04-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = 'h5c3'
down_revision: Union[str, Sequence[str], None] = 'g4b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('team_id', UUID(as_uuid=True), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='active'),
        sa.Column('payload', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_sessions_team_state', 'sessions', ['team_id', 'state'])
    op.create_index('ix_sessions_team_type', 'sessions', ['team_id', 'type'])
    op.create_index('ix_sessions_team_created_by', 'sessions', ['team_id', 'created_by'])

    op.add_column('issues', sa.Column('triage_context', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('issues', 'triage_context')
    op.drop_index('ix_sessions_team_created_by', table_name='sessions')
    op.drop_index('ix_sessions_team_type', table_name='sessions')
    op.drop_index('ix_sessions_team_state', table_name='sessions')
    op.drop_table('sessions')
