import uuid
from datetime import datetime

from pydantic import BaseModel

from taskstore.models.enums import StateType


class WorkflowStateCreate(BaseModel):
    name: str
    type: StateType
    color: str | None = None
    position: int = 0


class WorkflowStateResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    type: StateType
    color: str | None
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}
