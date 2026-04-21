import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

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
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _lowercase(cls, v: str) -> str:
        # Case-insensitive dedup — Alice@X.com and alice@x.com must
        # resolve to the same user.
        return v.lower()


class MembershipUpdate(BaseModel):
    """Body for PATCH /teams/{id}/members/{user_id} — OWNER-only
    endpoint that changes a member's role within the team."""

    model_config = {"extra": "forbid"}

    role: TeamRole


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: TeamRole
    created_at: datetime

    model_config = {"from_attributes": True}
