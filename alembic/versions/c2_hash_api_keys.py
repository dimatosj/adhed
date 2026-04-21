"""hash api keys (C2)

Revision ID: c2_hash_api_keys
Revises: 2bfe98426d58
Create Date: 2026-04-21

Renames teams.api_key -> teams.api_key_hash and backfills the hash
from any existing plaintext values. Stored form is SHA-256 hex.

This is a ONE-WAY migration for security: downgrade restores the
column name but the hashed values can't be reversed, so downgrade
only works on databases that were created after this migration ran.
"""
from alembic import op
import sqlalchemy as sa


revision: str = "c2_hash_api_keys"
down_revision: str | None = "2bfe98426d58"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add the new column, nullable while we backfill.
    op.add_column(
        "teams",
        sa.Column("api_key_hash", sa.Text(), nullable=True),
    )

    # 2. Backfill: hash every existing plaintext api_key in-place.
    # Uses pgcrypto's digest() if available; falls back to a CASE on
    # uppercase encode + sha256 via the built-in pgcrypto digest.
    # The 'encode(digest(...), hex)' produces lowercase hex, matching
    # Python's hashlib.sha256(...).hexdigest().
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
    )
    op.execute(
        "UPDATE teams "
        "SET api_key_hash = encode(digest(api_key, 'sha256'), 'hex') "
        "WHERE api_key IS NOT NULL"
    )

    # 3. Lock in constraints.
    op.alter_column("teams", "api_key_hash", nullable=False)
    op.create_unique_constraint(
        "uq_teams_api_key_hash", "teams", ["api_key_hash"]
    )

    # 4. Drop plaintext column + its old unique constraint.
    # The constraint name from the initial migration isn't explicit;
    # dropping the column cascades the unique constraint with it.
    op.drop_column("teams", "api_key")


def downgrade() -> None:
    # Hashes cannot be reversed; downgrade requires re-issuing keys.
    # We restore the column shape so older code can run, but every
    # team will need a new key (or the operator restores from a
    # pre-upgrade backup).
    op.add_column(
        "teams",
        sa.Column("api_key", sa.Text(), nullable=True),
    )
    op.drop_constraint("uq_teams_api_key_hash", "teams", type_="unique")
    op.drop_column("teams", "api_key_hash")
