import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db, get_team as get_authed_team
from taskstore.models.team import Team
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
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    label = await create_label(db, team_id, data)
    return Envelope(data=LabelResponse.model_validate(label))


@router.get(
    "/api/v1/teams/{team_id}/labels",
    response_model=Envelope[list[LabelResponse]],
)
async def list_labels_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
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
    db: AsyncSession = Depends(get_db),
):
    label = await get_label(db, label_id)
    if label.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    label = await update_label(db, label_id, data)
    return Envelope(data=LabelResponse.model_validate(label))


@router.delete(
    "/api/v1/labels/{label_id}",
    status_code=204,
)
async def delete_label_endpoint(
    label_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    label = await get_label(db, label_id)
    if label.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await delete_label(db, label_id)
