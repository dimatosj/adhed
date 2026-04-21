import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import (
    get_current_user,
    get_db,
    verified_team,
    verified_team_admin,
)
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.user import UserCreate, UserResponse
from taskstore.services.user_service import create_or_add_user, list_users

router = APIRouter(prefix="/api/v1/teams", tags=["users"])


@router.post("/{team_id}/users", response_model=Envelope[UserResponse], status_code=201)
async def create_user_endpoint(
    team_id: uuid.UUID,
    data: UserCreate,
    authed_team: Team = Depends(verified_team_admin),
    caller: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, role = await create_or_add_user(
        db, team_id, data, acting_user_id=caller.id
    )
    response = UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=role,
        created_at=user.created_at,
    )
    return Envelope(data=response)


@router.get("/{team_id}/users", response_model=Envelope[list[UserResponse]])
async def list_users_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
):
    members = await list_users(db, team_id)
    data = [
        UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=role,
            created_at=user.created_at,
        )
        for user, role in members
    ]
    return Envelope(data=data, meta=Meta(total=len(data)))
