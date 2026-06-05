import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_current_user, get_db, verified_team
from taskstore.api.deps import get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.recurrence import RecurrenceCreate, RecurrenceResponse, RecurrenceUpdate
from taskstore.services import recurrence_service

router = APIRouter(tags=["recurrences"])


@router.post(
    "/api/v1/teams/{team_id}/recurrences",
    response_model=Envelope[RecurrenceResponse],
    status_code=201,
)
async def create_recurrence_endpoint(
    team_id: uuid.UUID,
    data: RecurrenceCreate,
    team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rec = await recurrence_service.create_recurrence(db, team_id, user.id, data)
    return Envelope(data=rec)


@router.get(
    "/api/v1/teams/{team_id}/recurrences",
    response_model=Envelope[list[RecurrenceResponse]],
)
async def list_recurrences_endpoint(
    team_id: uuid.UUID,
    team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
    active: bool | None = Query(None),
    schedule_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    recurrences, total = await recurrence_service.list_recurrences(
        db,
        team_id,
        active=active,
        schedule_type=schedule_type,
        limit=limit,
        offset=offset,
    )
    return Envelope(data=recurrences, meta=Meta(total=total, limit=limit, offset=offset))


@router.get(
    "/api/v1/recurrences/{recurrence_id}",
    response_model=Envelope[RecurrenceResponse],
)
async def get_recurrence_endpoint(
    recurrence_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    raw = await recurrence_service.get_recurrence_raw(db, recurrence_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    response = await recurrence_service.get_recurrence(db, recurrence_id)
    return Envelope(data=response)


@router.patch(
    "/api/v1/recurrences/{recurrence_id}",
    response_model=Envelope[RecurrenceResponse],
)
async def update_recurrence_endpoint(
    recurrence_id: uuid.UUID,
    data: RecurrenceUpdate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await recurrence_service.get_recurrence_raw(db, recurrence_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    response = await recurrence_service.update_recurrence(db, recurrence_id, data, user.id)
    return Envelope(data=response)


@router.delete(
    "/api/v1/recurrences/{recurrence_id}",
    status_code=204,
)
async def delete_recurrence_endpoint(
    recurrence_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await recurrence_service.get_recurrence_raw(db, recurrence_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await recurrence_service.delete_recurrence(db, recurrence_id, user.id)
