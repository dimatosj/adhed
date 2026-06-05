import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from taskstore.database import Base
from taskstore.models.enums import ScheduleType
from taskstore.utils.time import now_utc


class Recurrence(Base):
    __tablename__ = "recurrences"
    __table_args__ = (
        Index("ix_recurrences_team", "team_id"),
        Index("ix_recurrences_due", "active", "next_due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title_template: Mapped[str] = mapped_column(String(500), nullable=False)
    description_template: Mapped[str | None] = mapped_column(Text)
    issue_defaults: Mapped[dict | None] = mapped_column(JSONB)
    schedule_type: Mapped[ScheduleType] = mapped_column(String(20), nullable=False)
    schedule_expr: Mapped[str] = mapped_column(String(100), nullable=False)
    next_due_at: Mapped[datetime] = mapped_column(nullable=False)
    last_spawned_at: Mapped[datetime | None] = mapped_column()
    last_spawned_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)
