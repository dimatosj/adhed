import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import (
    get_current_user,
    get_db,
    require_owner,
    verified_team,
    verified_team_admin,
    verified_team_owner,
)
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope
from taskstore.schemas.team import (
    ApiKeyRotateResponse,
    TeamCreate,
    TeamCreateResponse,
    TeamResponse,
    TeamUpdate,
)
from taskstore.services.team_service import (
    create_team,
    get_team,
    rotate_api_key,
    update_team,
)

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


@router.post("", response_model=Envelope[TeamCreateResponse], status_code=201)
async def create_team_endpoint(
    data: TeamCreate,
    caller: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    team, plaintext_key = await create_team(db, data, creator_user_id=caller.id)
    response = TeamCreateResponse(
        id=team.id,
        name=team.name,
        key=team.key,
        settings=team.settings,
        created_at=team.created_at,
        updated_at=team.updated_at,
        api_key=plaintext_key,
    )
    return Envelope(data=response)


@router.get("/{team_id}", response_model=Envelope[TeamResponse])
async def get_team_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
):
    team = await get_team(db, team_id)
    return Envelope(data=TeamResponse.model_validate(team))


@router.post(
    "/{team_id}/api-key/rotate",
    response_model=Envelope[ApiKeyRotateResponse],
)
async def rotate_api_key_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(verified_team_owner),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rotate the team's API key. OWNER only.

    The previous key stops authenticating immediately. The new
    plaintext key is returned exactly once — the server stores only
    its SHA-256 hash. Record it before closing the response.
    """
    team, new_plaintext = await rotate_api_key(db, team_id, user.id)
    return Envelope(
        data=ApiKeyRotateResponse(team_id=team.id, api_key=new_plaintext)
    )


@router.patch("/{team_id}", response_model=Envelope[TeamResponse])
async def update_team_endpoint(
    team_id: uuid.UUID,
    data: TeamUpdate,
    authed_team: Team = Depends(verified_team_admin),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    team = await update_team(db, team_id, data, user_id=user.id)
    return Envelope(data=TeamResponse.model_validate(team))
