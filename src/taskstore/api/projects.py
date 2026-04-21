import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
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
from taskstore.models.enums import ProjectState
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from taskstore.services.project_service import (
    create_project,
    delete_project,
    get_project,
    get_project_raw,
    list_projects,
    update_project,
)

router = APIRouter(tags=["projects"])


@router.post(
    "/api/v1/teams/{team_id}/projects",
    response_model=Envelope[ProjectResponse],
    status_code=201,
)
async def create_project_endpoint(
    team_id: uuid.UUID,
    data: ProjectCreate,
    authed_team: Team = Depends(verified_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await create_project(db, team_id, data, user_id=user.id)
    return Envelope(data=project)


@router.get(
    "/api/v1/teams/{team_id}/projects",
    response_model=Envelope[list[ProjectResponse]],
)
async def list_projects_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
    state: ProjectState | None = Query(None),
    lead_id: uuid.UUID | None = Query(None),
):
    projects = await list_projects(db, team_id, state=state, lead_id=lead_id)
    return Envelope(data=projects, meta=Meta(total=len(projects)))


@router.get(
    "/api/v1/projects/{project_id}",
    response_model=Envelope[ProjectResponse],
)
async def get_project_endpoint(
    project_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    raw = await get_project_raw(db, project_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    project = await get_project(db, project_id)
    return Envelope(data=project)


@router.patch(
    "/api/v1/projects/{project_id}",
    response_model=Envelope[ProjectResponse],
)
async def update_project_endpoint(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await get_project_raw(db, project_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    project = await update_project(db, project_id, data, user_id=user.id)
    return Envelope(data=project)


@router.delete(
    "/api/v1/projects/{project_id}",
    status_code=204,
)
async def delete_project_endpoint(
    project_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    caller: User = Depends(require_admin_or_owner),
    db: AsyncSession = Depends(get_db),
):
    raw = await get_project_raw(db, project_id)
    if raw.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await delete_project(db, project_id, user_id=caller.id)
