import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import (
    get_current_user,
    get_db,
    require_admin_or_owner,
    verified_team,
)
from taskstore.api.deps import (
    get_team as get_authed_team,
)
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.label import LabelCreate, LabelResponse, LabelUpdate
from taskstore.services.label_service import (
    create_label,
    delete_label,
    get_label,
    list_labels,
    update_label,
)

router = APIRouter(tags=["labels"])


@router.post(
    "/api/v1/teams/{team_id}/labels",
    response_model=Envelope[LabelResponse],
    status_code=201,
)
async def create_label_endpoint(
    team_id: uuid.UUID,
    data: LabelCreate,
    authed_team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    label = await create_label(db, team_id, data, user_id=user.id)
    return Envelope(data=LabelResponse.model_validate(label))


@router.get(
    "/api/v1/teams/{team_id}/labels",
    response_model=Envelope[list[LabelResponse]],
)
async def list_labels_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
):
    labels = await list_labels(db, team_id)
    return Envelope(
        data=[LabelResponse.model_validate(l) for l in labels],
        meta=Meta(total=len(labels)),
    )


@router.patch(
    "/api/v1/labels/{label_id}",
    response_model=Envelope[LabelResponse],
)
async def update_label_endpoint(
    label_id: uuid.UUID,
    data: LabelUpdate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    label = await get_label(db, label_id)
    if label.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    label = await update_label(db, label_id, data, user_id=user.id)
    return Envelope(data=LabelResponse.model_validate(label))


@router.delete(
    "/api/v1/labels/{label_id}",
    status_code=204,
)
async def delete_label_endpoint(
    label_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    caller: User = Depends(require_admin_or_owner),
    db: AsyncSession = Depends(get_db),
):
    label = await get_label(db, label_id)
    if label.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await delete_label(db, label_id, user_id=caller.id)
