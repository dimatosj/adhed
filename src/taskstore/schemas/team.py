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
    """Team record as returned from GET/PATCH. API key is intentionally
    not included — it is shown only once at creation time (see
    TeamCreateResponse and SetupResponse)."""

    id: uuid.UUID
    name: str
    key: str
    settings: TeamSettings
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamCreateResponse(TeamResponse):
    """Team creation returns the plaintext API key exactly once.
    Subsequent GET /teams/{id} calls return only TeamResponse (no key)."""

    api_key: str
