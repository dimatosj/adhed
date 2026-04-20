import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID | None
    rule_id: uuid.UUID | None
    issue_id: uuid.UUID | None
    message: str
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
