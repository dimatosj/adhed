import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from taskstore.models.enums import RuleTrigger


class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    trigger: RuleTrigger
    conditions: dict[str, Any]
    actions: list[dict[str, Any]] | dict[str, Any]
    priority: int = 100
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger: RuleTrigger | None = None
    conditions: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | dict[str, Any] | None = None
    priority: int | None = None
    enabled: bool | None = None


class RuleResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    description: str | None
    enabled: bool
    trigger: RuleTrigger
    conditions: dict[str, Any]
    actions: Any
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
