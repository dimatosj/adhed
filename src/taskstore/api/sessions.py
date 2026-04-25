import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_current_user, get_db, verified_team
from taskstore.api.deps import get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.session import SessionCreate, SessionResponse, SessionUpdate
from taskstore.services import session_service

router = APIRouter(tags=["sessions"])


@router.post(
    "/api/v1/teams/{team_id}/sessions",
    response_model=Envelope[SessionResponse],
    status_code=201,
)
async def create_session_endpoint(
    team_id: uuid.UUID,
    data: SessionCreate,
    team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.create_session(db, team_id, user.id, data)
    return Envelope(data=session)


@router.get(
    "/api/v1/teams/{team_id}/sessions",
    response_model=Envelope[list[SessionResponse]],
)
async def list_sessions_endpoint(
    team_id: uuid.UUID,
    team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
    type: str | None = Query(None),
    state: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    sessions, total = await session_service.list_sessions(
        db, team_id, session_type=type, state=state, limit=limit, offset=offset,
    )
    return Envelope(data=sessions, meta=Meta(total=total, limit=limit, offset=offset))


@router.get(
    "/api/v1/sessions/{session_id}",
    response_model=Envelope[SessionResponse],
)
async def get_session_endpoint(
    session_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    raw = await session_service.get_session_raw(db, session_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    response = await session_service.get_session(db, session_id)
    return Envelope(data=response)


@router.patch(
    "/api/v1/sessions/{session_id}",
    response_model=Envelope[SessionResponse],
)
async def update_session_endpoint(
    session_id: uuid.UUID,
    data: SessionUpdate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await session_service.get_session_raw(db, session_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    response = await session_service.update_session(db, session_id, data, user.id)
    return Envelope(data=response)
