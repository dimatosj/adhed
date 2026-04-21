import uuid
from datetime import datetime

from pydantic import BaseModel

from taskstore.models.enums import TeamRole


class UserCreate(BaseModel):
    """Fields a client may supply when adding a user to a team.

    `role` is intentionally excluded — roles are assigned server-side
    based on team-membership ordering (first member → OWNER, rest →
    MEMBER). Accepting a client-supplied role would let any API-key
    holder mint OWNER memberships (S3).
    """

    model_config = {"extra": "forbid"}

    name: str
    email: str


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: TeamRole
    created_at: datetime

    model_config = {"from_attributes": True}
