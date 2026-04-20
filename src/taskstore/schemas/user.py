import uuid
from datetime import datetime

from pydantic import BaseModel

from taskstore.models.enums import TeamRole


class UserCreate(BaseModel):
    name: str
    email: str
    role: TeamRole | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: TeamRole
    created_at: datetime

    model_config = {"from_attributes": True}
