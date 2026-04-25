import uuid
from datetime import datetime

from sqlalchemy import Computed, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from taskstore.database import Base
from taskstore.models.enums import FragmentType
from taskstore.utils.time import now_utc


class Fragment(Base):
    __tablename__ = "fragments"
    __table_args__ = (
        Index("ix_fragments_team_created", "team_id", "created_at"),
        Index("ix_fragments_team_type", "team_id", "type"),
        Index("ix_fragments_topics", "topics", postgresql_using="gin"),
        Index("ix_fragments_domains", "domains", postgresql_using="gin"),
        Index("ix_fragments_entities", "entities", postgresql_using="gin"),
        Index("ix_fragments_text_search", "text_search", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[FragmentType] = mapped_column(nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    topics: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    domains: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    entities: Mapped[dict | None] = mapped_column(JSONB)
    subtype: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)
    text_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(text, '') || ' ' || coalesce(summary, ''))", persisted=True),
    )
