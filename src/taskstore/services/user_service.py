import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import record_audit
from taskstore.models.enums import AuditAction, TeamRole
from taskstore.models.user import TeamMembership, User
from taskstore.schemas.user import UserCreate


async def create_or_add_user(
    db: AsyncSession,
    team_id: uuid.UUID,
    data: UserCreate,
    acting_user_id: uuid.UUID | None = None,
) -> tuple[User, TeamRole]:
    # Check if user with this email already exists
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(name=data.name, email=data.email)
        db.add(user)
        await db.flush()

    # Check if already a member of this team
    membership_result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == user.id,
            TeamMembership.team_id == team_id,
        )
    )
    existing_membership = membership_result.scalar_one_or_none()

    if existing_membership is not None:
        await db.commit()
        await db.refresh(user)
        return user, existing_membership.role

    # Role is assigned server-side — first member of a team becomes OWNER,
    # all subsequent members default to MEMBER. Client-supplied roles are
    # rejected at the schema layer (see UserCreate) to prevent privilege
    # escalation.
    count_result = await db.execute(
        select(func.count()).where(TeamMembership.team_id == team_id)
    )
    member_count = count_result.scalar()
    role = TeamRole.OWNER if member_count == 0 else TeamRole.MEMBER

    membership = TeamMembership(user_id=user.id, team_id=team_id, role=role)
    db.add(membership)
    if acting_user_id is not None:
        # Audits track who added whom. For the /setup bootstrap path
        # there is no acting user yet — the first call passes None.
        await record_audit(
            db, team_id, "membership", user.id, AuditAction.CREATE, acting_user_id
        )
    await db.commit()
    await db.refresh(user)
    return user, role


async def change_member_role(
    db: AsyncSession,
    team_id: uuid.UUID,
    target_user_id: uuid.UUID,
    new_role: TeamRole,
    acting_user_id: uuid.UUID,
) -> tuple[User, TeamRole]:
    """Change a team member's role. OWNER-only (enforced at endpoint).

    Refuses to demote the last OWNER — otherwise the team becomes
    unmanageable (no one can rotate keys, add members, etc.).
    """
    from fastapi import HTTPException

    membership_result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == target_user_id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    # Guard against last-owner demotion.
    if membership.role == TeamRole.OWNER and new_role != TeamRole.OWNER:
        owner_count_result = await db.execute(
            select(func.count()).where(
                TeamMembership.team_id == team_id,
                TeamMembership.role == TeamRole.OWNER,
            )
        )
        owner_count = owner_count_result.scalar()
        if owner_count <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot demote the last owner — promote another member to owner first.",
            )

    membership.role = new_role
    await record_audit(
        db, team_id, "membership", target_user_id, AuditAction.UPDATE, acting_user_id
    )
    await db.commit()

    user_result = await db.execute(select(User).where(User.id == target_user_id))
    user = user_result.scalar_one()
    return user, new_role


async def list_users(db: AsyncSession, team_id: uuid.UUID) -> list[tuple[User, TeamRole]]:
    result = await db.execute(
        select(User, TeamMembership.role)
        .join(TeamMembership, User.id == TeamMembership.user_id)
        .where(TeamMembership.team_id == team_id)
    )
    return [(row[0], row[1]) for row in result.all()]
