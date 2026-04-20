import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.defaults import seed_default_states
from taskstore.models.team import Team
from taskstore.schemas.team import TeamCreate, TeamUpdate


async def create_team(db: AsyncSession, data: TeamCreate) -> Team:
    team = Team(
        name=data.name,
        key=data.key.upper(),
        api_key=f"ts_{secrets.token_hex(32)}",
    )
    db.add(team)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Team key '{data.key}' already exists")
    await seed_default_states(db, team.id)
    await db.commit()
    await db.refresh(team)
    return team


async def get_team(db: AsyncSession, team_id: uuid.UUID) -> Team:
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def update_team(db: AsyncSession, team_id: uuid.UUID, data: TeamUpdate) -> Team:
    team = await get_team(db, team_id)
    if data.name is not None:
        team.name = data.name
    if data.settings is not None:
        team.settings = data.settings.model_dump()
    await db.commit()
    await db.refresh(team)
    return team
