import uuid
from datetime import datetime

from pydantic import BaseModel

from taskstore.models.enums import ScheduleType


class RecurrenceCreate(BaseModel):
    title_template: str
    description_template: str | None = None
    issue_defaults: dict | None = None
    schedule_type: ScheduleType
    schedule_expr: str
    next_due_at: datetime | None = None


class RecurrenceUpdate(BaseModel):
    title_template: str | None = None
    description_template: str | None = None
    issue_defaults: dict | None = None
    schedule_type: ScheduleType | None = None
    schedule_expr: str | None = None
    next_due_at: datetime | None = None
    active: bool | None = None


class RecurrenceResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    created_by: uuid.UUID
    title_template: str
    description_template: str | None
    issue_defaults: dict | None
    schedule_type: ScheduleType
    schedule_expr: str
    next_due_at: datetime
    last_spawned_at: datetime | None
    last_spawned_issue_id: uuid.UUID | None
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
