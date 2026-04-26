import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from taskstore.database import Base
from taskstore.models.enums import SessionState, SessionType
from taskstore.utils.time import now_utc


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_team_state", "team_id", "state"),
        Index("ix_sessions_team_type", "team_id", "type"),
        Index("ix_sessions_team_created_by", "team_id", "created_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type: Mapped[SessionType] = mapped_column(String(20), nullable=False)
    state: Mapped[SessionState] = mapped_column(String(20), default=SessionState.ACTIVE)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column()
