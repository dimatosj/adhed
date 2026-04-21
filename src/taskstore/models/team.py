import hashlib
import uuid
from datetime import datetime

from taskstore.utils.time import now_utc

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from taskstore.database import Base


def hash_api_key(plaintext: str) -> str:
    """SHA-256 hash the plaintext API key for storage and lookup.

    API keys are 256-bit random tokens (not user passwords), so salted
    password hashes (bcrypt, argon2) are the wrong primitive — they'd
    prevent indexed lookup without gaining security. SHA-256 of a
    256-bit random input has infeasible preimages; indexed equality
    is the standard pattern for API token auth.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default={"archive_days": 30, "triage_enabled": True})
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        default=now_utc,
        onupdate=now_utc,
    )
