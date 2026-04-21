import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import record_audit
from taskstore.engine.defaults import seed_default_states
from taskstore.models.enums import AuditAction, TeamRole
from taskstore.models.team import Team, hash_api_key
from taskstore.models.user import TeamMembership
from taskstore.schemas.team import TeamCreate, TeamUpdate


async def create_team(
    db: AsyncSession,
    data: TeamCreate,
    creator_user_id: uuid.UUID | None = None,
) -> tuple[Team, str]:
    """Create a team. Returns (team, plaintext_api_key).

    The plaintext API key is shown to the caller exactly once — it is
    NOT recoverable after this. The DB stores only the SHA-256 hash.

    If ``creator_user_id`` is given, the creator is added as an OWNER
    of the new team — otherwise the team has zero members and is
    effectively unusable (no one can mint further users). Callers from
    /setup pass None because they add the user separately.
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
    if creator_user_id is not None:
        db.add(TeamMembership(
            team_id=team.id,
            user_id=creator_user_id,
            role=TeamRole.OWNER,
        ))
    await db.commit()
    await db.refresh(team)
    return team, plaintext_key


async def get_team(db: AsyncSession, team_id: uuid.UUID) -> Team:
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def rotate_api_key(
    db: AsyncSession,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[Team, str]:
    """Generate a new API key, store its hash, invalidate the old one.

    Returns (team, new_plaintext_key). The plaintext is shown to the
    caller exactly once. Audit-logged as an `update` on `team_api_key`.
    """
    team = await get_team(db, team_id)
    new_plaintext = f"adhed_{secrets.token_hex(32)}"
    team.api_key_hash = hash_api_key(new_plaintext)
    await record_audit(
        db, team.id, "team_api_key", team.id, AuditAction.UPDATE, user_id
    )
    await db.commit()
    await db.refresh(team)
    return team, new_plaintext


async def update_team(
    db: AsyncSession,
    team_id: uuid.UUID,
    data: TeamUpdate,
    user_id: uuid.UUID | None = None,
) -> Team:
    team = await get_team(db, team_id)
    if data.name is not None:
        team.name = data.name
    if data.settings is not None:
        team.settings = data.settings.model_dump()
    if user_id is not None:
        await record_audit(
            db, team.id, "team", team.id, AuditAction.UPDATE, user_id
        )
    await db.commit()
    await db.refresh(team)
    return team
