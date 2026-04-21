import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.database import create_session_factory
from taskstore.models.enums import TeamRole
from taskstore.models.team import Team, hash_api_key
from taskstore.models.user import TeamMembership, User

logger = logging.getLogger(__name__)

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
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Team:
    client_ip = request.client.host if request.client else "unknown"
    if not x_api_key:
        logger.warning(
            "auth_missing_api_key",
            extra={"client_ip": client_ip, "path": request.url.path},
        )
        raise HTTPException(status_code=401, detail="Missing API key")
    result = await db.execute(
        select(Team).where(Team.api_key_hash == hash_api_key(x_api_key))
    )
    team = result.scalar_one_or_none()
    if not team:
        logger.warning(
            "auth_invalid_api_key",
            extra={"client_ip": client_ip, "path": request.url.path},
        )
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


async def verified_team(
    team_id: uuid.UUID,
    team: Team = Depends(get_team),
) -> Team:
    """Require X-API-Key AND verify the path's team_id matches the authed team.

    Replaces the 25+ copies of manual `if authed_team.id != team_id: raise 403`
    that used to live inside every endpoint.
    """
    if team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return team


async def _caller_role(
    team_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> TeamRole | None:
    result = await db.execute(
        select(TeamMembership.role).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


def require_role_in_authed_team(*required: TeamRole):
    """Dep factory: require the caller to hold one of the given roles
    in the authed team (the team identified by X-API-Key).

    Use for endpoints whose path doesn't include {team_id} but which
    still need a role gate (e.g. POST /teams, PATCH /rules/{rule_id},
    DELETE /labels/{label_id}).
    """

    async def dep(
        team: Team = Depends(get_team),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        role = await _caller_role(team.id, user.id, db)
        if role not in required:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return dep


def require_role_in_path_team(*required: TeamRole):
    """Dep factory: verified_team + role check, for endpoints that take
    {team_id} in the path.
    """

    async def dep(
        team_id: uuid.UUID,
        team: Team = Depends(get_team),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Team:
        if team.id != team_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        role = await _caller_role(team.id, user.id, db)
        if role not in required:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return team

    return dep


# Named deps for the common role sets. Reusing module-level functions
# (not constructing new deps per request) keeps FastAPI's dep graph
# deduplicated.
require_owner = require_role_in_authed_team(TeamRole.OWNER)
require_admin_or_owner = require_role_in_authed_team(TeamRole.ADMIN, TeamRole.OWNER)
verified_team_admin = require_role_in_path_team(TeamRole.ADMIN, TeamRole.OWNER)
