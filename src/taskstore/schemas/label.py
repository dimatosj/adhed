import uuid
from datetime import datetime

from pydantic import BaseModel


class LabelCreate(BaseModel):
    name: str
    color: str | None = None
    description: str | None = None


class LabelUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    description: str | None = None


class LabelResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    color: str | None
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
