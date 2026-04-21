import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.defaults import seed_default_states
from taskstore.models.team import Team, hash_api_key
from taskstore.schemas.team import TeamCreate, TeamUpdate


async def create_team(db: AsyncSession, data: TeamCreate) -> tuple[Team, str]:
    """Create a team. Returns (team, plaintext_api_key).

    The plaintext API key is shown to the caller exactly once — it is
    NOT recoverable after this. The DB stores only the SHA-256 hash.
    """
    plaintext_key = f"adhed_{secrets.token_hex(32)}"
    team = Team(
        name=data.name,
        key=data.key.upper(),
        api_key_hash=hash_api_key(plaintext_key),
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
    return team, plaintext_key


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
