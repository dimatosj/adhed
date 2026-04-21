import uuid
from datetime import date, datetime

from taskstore.utils.time import now_utc

from sqlalchemy import Computed, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from taskstore.database import Base
from taskstore.models.enums import IssueType


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        Index("ix_issues_team_state", "team_id", "state_id"),
        Index("ix_issues_team_assignee", "team_id", "assignee_id"),
        Index("ix_issues_team_project", "team_id", "project_id"),
        Index("ix_issues_team_parent", "team_id", "parent_id"),
        Index("ix_issues_team_due", "team_id", "due_date"),
        Index("ix_issues_team_created_by", "team_id", "created_by"),
        Index("ix_issues_title_search", "title_search", postgresql_using="gin"),
        Index("ix_issues_custom_fields", "custom_fields", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[IssueType] = mapped_column(default=IssueType.TASK)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    estimate: Mapped[int | None] = mapped_column(Integer)
    state_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_states.id"), nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("issues.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    custom_fields: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        default=now_utc,
        onupdate=now_utc,
    )
    archived_at: Mapped[datetime | None] = mapped_column()
    title_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))", persisted=True),
    )


class IssueLabel(Base):
    __tablename__ = "issue_labels"

    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True)
    label_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True)
