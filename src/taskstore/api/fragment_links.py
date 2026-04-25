import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_current_user, get_db
from taskstore.api.deps import get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.fragment_link import FragmentLinkCreate, FragmentLinkResponse
from taskstore.services import fragment_link_service

router = APIRouter(tags=["fragment-links"])


@router.post(
    "/api/v1/fragments/{fragment_id}/links",
    response_model=Envelope[FragmentLinkResponse],
    status_code=201,
)
async def create_link(
    fragment_id: uuid.UUID,
    data: FragmentLinkCreate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link = await fragment_link_service.create_link(
        db, fragment_id, data.target_type, data.target_id, user.id, authed_team.id,
    )
    return Envelope(data=link)


@router.get(
    "/api/v1/fragments/{fragment_id}/links",
    response_model=Envelope[list[FragmentLinkResponse]],
)
async def get_links(
    fragment_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
    target_type: str | None = Query(None),
):
    links = await fragment_link_service.get_links(
        db, fragment_id, authed_team.id, target_type_filter=target_type,
    )
    return Envelope(data=links, meta=Meta(total=len(links)))


@router.delete(
    "/api/v1/fragments/{fragment_id}/links/{link_id}",
    status_code=204,
)
async def delete_link(
    fragment_id: uuid.UUID,
    link_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await fragment_link_service.delete_link(db, fragment_id, link_id, user.id, authed_team.id)
