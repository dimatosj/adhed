import uuid
from datetime import datetime

from pydantic import BaseModel


class FragmentLinkCreate(BaseModel):
    target_type: str
    target_id: uuid.UUID


class FragmentLinkResponse(BaseModel):
    id: uuid.UUID
    direction: str
    target_type: str
    target_id: uuid.UUID
    summary: str
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}
