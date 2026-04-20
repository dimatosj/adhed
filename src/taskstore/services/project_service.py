import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.models.enums import ProjectState
from taskstore.models.issue import Issue
from taskstore.models.project import Project
from taskstore.models.workflow_state import WorkflowState
from taskstore.schemas.project import IssueCounts, ProjectCreate, ProjectResponse, ProjectUpdate


async def _build_response(
    db: AsyncSession, project: Project, *, include_counts: bool = False
) -> ProjectResponse:
    resp = ProjectResponse(
        id=project.id,
        team_id=project.team_id,
        name=project.name,
        description=project.description,
        state=project.state,
        lead_id=project.lead_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
    if include_counts:
        resp.issue_counts = await _get_issue_counts(db, project.id)
    return resp


async def _get_issue_counts(db: AsyncSession, project_id: uuid.UUID) -> IssueCounts:
    result = await db.execute(
        select(WorkflowState.type, func.count(Issue.id))
        .join(WorkflowState, Issue.state_id == WorkflowState.id)
        .where(Issue.project_id == project_id)
        .group_by(WorkflowState.type)
    )
    counts = {row[0].value: row[1] for row in result.all()}
    return IssueCounts(
        triage=counts.get("triage", 0),
        backlog=counts.get("backlog", 0),
        unstarted=counts.get("unstarted", 0),
        started=counts.get("started", 0),
        completed=counts.get("completed", 0),
        canceled=counts.get("canceled", 0),
    )


async def create_project(
    db: AsyncSession, team_id: uuid.UUID, data: ProjectCreate
) -> ProjectResponse:
    project = Project(team_id=team_id, **data.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _build_response(db, project)


async def list_projects(
    db: AsyncSession,
    team_id: uuid.UUID,
    *,
    state: ProjectState | None = None,
    lead_id: uuid.UUID | None = None,
) -> list[ProjectResponse]:
    query = select(Project).where(Project.team_id == team_id)
    if state is not None:
        query = query.where(Project.state == state)
    if lead_id is not None:
        query = query.where(Project.lead_id == lead_id)
    query = query.order_by(Project.created_at.desc())
    result = await db.execute(query)
    projects = list(result.scalars().all())
    return [await _build_response(db, p) for p in projects]


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _build_response(db, project, include_counts=True)


async def get_project_raw(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def update_project(
    db: AsyncSession, project_id: uuid.UUID, data: ProjectUpdate
) -> ProjectResponse:
    project = await get_project_raw(db, project_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return await _build_response(db, project, include_counts=True)


async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    project = await get_project_raw(db, project_id)

    # Check for any issues in this project
    result = await db.execute(
        select(func.count()).select_from(Issue).where(Issue.project_id == project_id)
    )
    issue_count = result.scalar_one()
    if issue_count > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete project with issues",
        )

    await db.delete(project)
    await db.commit()
