import uuid
from datetime import datetime

from pydantic import BaseModel

from taskstore.models.enums import ProjectState


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    state: ProjectState = ProjectState.PLANNED
    lead_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    state: ProjectState | None = None
    lead_id: uuid.UUID | None = None


class IssueCounts(BaseModel):
    triage: int = 0
    backlog: int = 0
    unstarted: int = 0
    started: int = 0
    completed: int = 0
    canceled: int = 0


class ProjectResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    description: str | None
    state: ProjectState
    lead_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    issue_counts: IssueCounts | None = None

    model_config = {"from_attributes": True}
