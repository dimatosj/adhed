import uuid
from typing import AsyncGenerator

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.database import create_session_factory
from taskstore.models.team import Team
from taskstore.models.user import User, TeamMembership

_session_factory = None


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory()
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_team(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Team:
    result = await db.execute(select(Team).where(Team.api_key == x_api_key))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return team


async def get_current_user(
    x_user_id: str = Header(..., alias="X-User-Id"),
    team: Team = Depends(get_team),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id format")

    result = await db.execute(
        select(User)
        .join(TeamMembership)
        .where(TeamMembership.team_id == team.id, User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=403, detail="User is not a member of this team")
    return user
