import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import (
    _caller_role,
    get_current_user,
    get_db,
    get_team as get_authed_team,
    verified_team,
)
from taskstore.models.audit import AuditEntry
from taskstore.models.enums import AuditAction, TeamRole
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.audit import AuditResponse
from taskstore.schemas.common import Envelope, Meta

router = APIRouter(tags=["audit"])


@router.get(
    "/api/v1/teams/{team_id}/audit",
    response_model=Envelope[list[AuditResponse]],
)
async def list_audit_entries(
    team_id: uuid.UUID,
    authed_team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    entity_type: str | None = Query(None),
    entity_id: uuid.UUID | None = Query(None),
    action: AuditAction | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    after: datetime | None = Query(None),
    before: datetime | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    # MEMBER role sees only their own audit entries; ADMIN/OWNER see all.
    # Any incoming user_id filter is overridden for MEMBERs so they can't
    # probe for others' activity.
    role = await _caller_role(authed_team.id, user.id, db)
    if role == TeamRole.MEMBER:
        user_id = user.id

    query = select(AuditEntry).where(AuditEntry.team_id == team_id)

    if entity_type is not None:
        query = query.where(AuditEntry.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditEntry.entity_id == entity_id)
    if action is not None:
        query = query.where(AuditEntry.action == action)
    if user_id is not None:
        query = query.where(AuditEntry.user_id == user_id)
    if after is not None:
        query = query.where(AuditEntry.created_at > after)
    if before is not None:
        query = query.where(AuditEntry.created_at < before)

    # H4: use func.count() rather than materializing every row's id.
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(AuditEntry.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    entries = list(result.scalars().all())

    return Envelope(
        data=[AuditResponse.model_validate(e) for e in entries],
        meta=Meta(total=total, limit=limit, offset=offset),
    )
