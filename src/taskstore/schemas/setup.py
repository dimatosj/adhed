import uuid
from pydantic import BaseModel


class SetupRequest(BaseModel):
    team_name: str
    team_key: str
    user_name: str
    user_email: str


class SetupResponse(BaseModel):
    team_id: uuid.UUID
    team_name: str
    team_key: str
    api_key: str
    user_id: uuid.UUID
    user_name: str
    user_email: str
