import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db, get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.schemas.common import Envelope
from taskstore.schemas.team import TeamCreate, TeamResponse, TeamSettings, TeamUpdate
from taskstore.services.team_service import create_team, get_team, update_team

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


@router.post("", response_model=Envelope[TeamResponse], status_code=201)
async def create_team_endpoint(data: TeamCreate, db: AsyncSession = Depends(get_db)):
    team = await create_team(db, data)
    return Envelope(data=TeamResponse.model_validate(team))


@router.get("/{team_id}", response_model=Envelope[TeamResponse])
async def get_team_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    team = await get_team(db, team_id)
    return Envelope(data=TeamResponse.model_validate(team))


@router.patch("/{team_id}", response_model=Envelope[TeamResponse])
async def update_team_endpoint(
    team_id: uuid.UUID,
    data: TeamUpdate,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    team = await update_team(db, team_id, data)
    return Envelope(data=TeamResponse.model_validate(team))
