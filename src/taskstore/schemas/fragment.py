import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from taskstore.models.enums import FragmentType


class FragmentSource(BaseModel):
    room: str | None = None
    linked_project_id: str | None = None
    linked_issue_id: str | None = None
    conversation_timestamp: str | None = None
    unresolved_reference: str | None = None


class FragmentCreate(BaseModel):
    text: str
    type: FragmentType
    summary: str | None = None
    subtype: str | None = None
    source_url: str | None = None
    topics: list[str] | None = Field(default=None, max_length=3)
    domains: list[str] | None = None
    entities: list[dict] | None = None
    source: FragmentSource | None = None


class FragmentUpdate(BaseModel):
    text: str | None = None
    type: FragmentType | None = None
    summary: str | None = None
    subtype: str | None = None
    source_url: str | None = None
    topics: list[str] | None = Field(default=None, max_length=3)
    domains: list[str] | None = None
    entities: list[dict] | None = None
    source: FragmentSource | None = None


class FragmentResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    text: str
    type: FragmentType
    summary: str | None
    subtype: str | None
    source_url: str | None
    topics: list[str] | None
    domains: list[str] | None
    entities: list[dict] | None
    source: dict | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopicCount(BaseModel):
    topic: str
    count: int
