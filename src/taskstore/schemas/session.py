import uuid
from datetime import datetime

from pydantic import BaseModel

from taskstore.models.enums import SessionState, SessionType


class SessionCreate(BaseModel):
    type: SessionType
    payload: dict | None = None


class SessionUpdate(BaseModel):
    state: SessionState | None = None
    payload: dict | None = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    created_by: uuid.UUID
    type: SessionType
    state: SessionState
    payload: dict | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
