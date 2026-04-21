import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_current_user, get_db, get_team as get_authed_team, verified_team
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.issue import IssueCreate, IssueResponse, IssueUpdate
from taskstore.services.issue_service import (
    batch_create_issues,
    batch_update_issues,
    convert_to_project,
    create_issue,
    delete_issue,
    get_issue,
    get_issue_raw,
    list_issues,
    update_issue,
)

router = APIRouter(tags=["issues"])


@router.post(
    "/api/v1/teams/{team_id}/issues",
    response_model=Envelope[IssueResponse],
    status_code=201,
)
async def create_issue_endpoint(
    team_id: uuid.UUID,
    data: IssueCreate,
    authed_team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    response = await create_issue(db, authed_team, data, user.id)
    return Envelope(data=response)


@router.get(
    "/api/v1/teams/{team_id}/issues",
    response_model=Envelope[list[IssueResponse]],
)
async def list_issues_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
    state_type: str | None = Query(None),
    assignee: uuid.UUID | None = Query(None),
    project_id: str | None = Query(None),
    parent_id: str | None = Query(None),
    label: str | None = Query(None),
    priority: str | None = Query(None),
    type: str | None = Query(None),
    created_by: uuid.UUID | None = Query(None),
    due_before: date | None = Query(None),
    due_after: date | None = Query(None),
    overdue: bool | None = Query(None),
    title_search: str | None = Query(None),
    estimate_lte: int | None = Query(None),
    estimate_gte: int | None = Query(None),
    archived: bool = Query(False),
    limit: int = Query(50),
    offset: int = Query(0),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
):
    issues, total = await list_issues(
        db,
        team_id,
        state_type=state_type,
        assignee=assignee,
        project_id=project_id,
        parent_id=parent_id,
        label=label,
        priority=priority,
        type=type,
        created_by=created_by,
        due_before=due_before,
        due_after=due_after,
        overdue=overdue,
        title_search=title_search,
        estimate_lte=estimate_lte,
        estimate_gte=estimate_gte,
        archived=archived,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )
    return Envelope(data=issues, meta=Meta(total=total, limit=limit, offset=offset))


@router.get(
    "/api/v1/issues/{issue_id}",
    response_model=Envelope[IssueResponse],
)
async def get_issue_endpoint(
    issue_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    raw = await get_issue_raw(db, issue_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    response = await get_issue(db, issue_id)
    return Envelope(data=response)


@router.patch(
    "/api/v1/issues/{issue_id}",
    response_model=Envelope[IssueResponse],
)
async def update_issue_endpoint(
    issue_id: uuid.UUID,
    data: IssueUpdate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await get_issue_raw(db, issue_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    response = await update_issue(db, issue_id, data, user_id=user.id)
    return Envelope(data=response)


@router.delete(
    "/api/v1/issues/{issue_id}",
    status_code=204,
)
async def delete_issue_endpoint(
    issue_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await get_issue_raw(db, issue_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await delete_issue(db, issue_id)


@router.post(
    "/api/v1/teams/{team_id}/issues/batch",
    status_code=200,
)
async def batch_create_issues_endpoint(
    team_id: uuid.UUID,
    items: list[IssueCreate],
    authed_team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await batch_create_issues(db, authed_team, items, user.id)
    return Envelope(data=results)


class BatchUpdateBody(BaseModel):
    filter: dict[str, Any]
    update: dict[str, Any]


@router.patch(
    "/api/v1/teams/{team_id}/issues/batch",
    status_code=200,
)
async def batch_update_issues_endpoint(
    team_id: uuid.UUID,
    body: BatchUpdateBody,
    authed_team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await batch_update_issues(
        db, team_id, body.filter, body.update, user_id=user.id
    )
    return Envelope(data=results)


@router.post(
    "/api/v1/issues/{issue_id}/convert-to-project",
    status_code=201,
)
async def convert_issue_to_project_endpoint(
    issue_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    raw = await get_issue_raw(db, issue_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    result = await convert_to_project(db, issue_id)
    return Envelope(data=result)
