import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_current_user, get_db, verified_team
from taskstore.api.deps import get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.fragment import FragmentCreate, FragmentResponse, FragmentUpdate, TopicCount
from taskstore.services import fragment_service

router = APIRouter(tags=["fragments"])


@router.post(
    "/api/v1/teams/{team_id}/fragments",
    response_model=Envelope[FragmentResponse],
    status_code=201,
)
async def create_fragment(
    team_id: uuid.UUID,
    data: FragmentCreate,
    team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    frag = await fragment_service.create_fragment(db, team_id, user.id, data)
    return Envelope(data=frag)


@router.get(
    "/api/v1/teams/{team_id}/fragments",
    response_model=Envelope[list[FragmentResponse]],
)
async def list_fragments(
    team_id: uuid.UUID,
    team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
    type: str | None = Query(None),
    subtype: str | None = Query(None),
    domain: str | None = Query(None),
    topic: str | None = Query(None),
    project_id: str | None = Query(None),
    issue_id: str | None = Query(None),
    entity_name: str | None = Query(None),
    title_search: str | None = Query(None),
    created_by: uuid.UUID | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
):
    fragments, total = await fragment_service.list_fragments(
        db, team_id,
        fragment_type=type.split(",") if type else None,
        subtype=subtype.split(",") if subtype else None,
        domain=domain.split(",") if domain else None,
        topic=topic,
        project_id=project_id,
        issue_id=issue_id,
        entity_name=entity_name,
        title_search=title_search,
        created_by=created_by,
        limit=limit, offset=offset, sort=sort, order=order,
    )
    return Envelope(data=fragments, meta=Meta(total=total, limit=limit, offset=offset))


@router.get(
    "/api/v1/teams/{team_id}/fragments/topics",
    response_model=Envelope[list[TopicCount]],
)
async def list_topics(
    team_id: uuid.UUID,
    team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
):
    topics = await fragment_service.list_topics(db, team_id)
    return Envelope(data=topics)


@router.get(
    "/api/v1/fragments/{fragment_id}",
    response_model=Envelope[FragmentResponse],
)
async def get_fragment(
    fragment_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    frag = await fragment_service.get_fragment(db, fragment_id)
    if frag.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return Envelope(data=frag)


@router.patch(
    "/api/v1/fragments/{fragment_id}",
    response_model=Envelope[FragmentResponse],
)
async def update_fragment(
    fragment_id: uuid.UUID,
    data: FragmentUpdate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    frag = await fragment_service.get_fragment(db, fragment_id)
    if frag.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    frag = await fragment_service.update_fragment(db, fragment_id, user.id, data)
    return Envelope(data=frag)


@router.delete("/api/v1/fragments/{fragment_id}", status_code=204)
async def delete_fragment(
    fragment_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    frag = await fragment_service.get_fragment(db, fragment_id)
    if frag.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await fragment_service.delete_fragment(db, fragment_id, user.id)
