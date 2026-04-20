import uuid
from datetime import datetime

from pydantic import BaseModel


class TeamSettings(BaseModel):
    archive_days: int = 30
    triage_enabled: bool = True


class TeamCreate(BaseModel):
    name: str
    key: str


class TeamUpdate(BaseModel):
    name: str | None = None
    settings: TeamSettings | None = None


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    key: str
    api_key: str
    settings: TeamSettings
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
