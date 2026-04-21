import uuid

from pydantic import BaseModel, EmailStr, field_validator


class SetupRequest(BaseModel):
    team_name: str
    team_key: str
    user_name: str
    user_email: EmailStr
    # When true, seed the 14 GTD-flavored default labels. Off by default
    # since they're opinionated and a fresh public user may not want them.
    include_default_labels: bool = False

    @field_validator("user_email", mode="after")
    @classmethod
    def _lowercase(cls, v: str) -> str:
        return v.lower()


class SetupResponse(BaseModel):
    team_id: uuid.UUID
    team_name: str
    team_key: str
    api_key: str
    user_id: uuid.UUID
    user_name: str
    user_email: str
