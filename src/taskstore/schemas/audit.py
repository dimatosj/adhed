import uuid
from datetime import datetime

from pydantic import BaseModel

from taskstore.models.enums import AuditAction


class AuditResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    action: AuditAction
    user_id: uuid.UUID
    changes: dict
    created_at: datetime

    model_config = {"from_attributes": True}
