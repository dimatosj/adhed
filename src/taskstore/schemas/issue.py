import json
import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator

from taskstore.models.enums import IssueType, StateType

# Cap at which custom_fields is rejected at ingress. Prevents
# unbounded JSONB growth and keeps the GIN index small. Raise it
# via env if you have a real use case for bigger payloads.
_MAX_CUSTOM_FIELDS_BYTES = 16 * 1024  # 16 KiB


def _check_custom_fields(value: dict | None) -> dict | None:
    if value is None:
        return None
    size = len(json.dumps(value, default=str))
    if size > _MAX_CUSTOM_FIELDS_BYTES:
        raise ValueError(
            f"custom_fields exceeds {_MAX_CUSTOM_FIELDS_BYTES} byte limit "
            f"(got {size} bytes)"
        )
    return value


class IssueStateInfo(BaseModel):
    id: uuid.UUID
    name: str
    type: StateType

    model_config = {"from_attributes": True}


class IssueLabelInfo(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class IssueCreate(BaseModel):
    title: str
    description: str | None = None
    type: IssueType = IssueType.TASK
    priority: int = 0
    estimate: int | None = None
    state_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    due_date: date | None = None
    custom_fields: dict | None = None
    label_ids: list[uuid.UUID] | None = None

    _check_cf = field_validator("custom_fields")(_check_custom_fields)


class IssueUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    type: IssueType | None = None
    priority: int | None = None
    estimate: int | None = None
    state_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    due_date: date | None = None
    custom_fields: dict | None = None

    _check_cf = field_validator("custom_fields")(_check_custom_fields)


class IssueResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    title: str
    description: str | None
    type: IssueType
    priority: int
    estimate: int | None
    state: IssueStateInfo
    assignee_id: uuid.UUID | None
    project_id: uuid.UUID | None
    parent_id: uuid.UUID | None
    due_date: date | None
    custom_fields: dict | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    labels: list[IssueLabelInfo] = []

    model_config = {"from_attributes": True}
