import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db, get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.models.workflow_state import WorkflowState
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.workflow_state import WorkflowStateCreate, WorkflowStateResponse

router = APIRouter(prefix="/api/v1/teams", tags=["states"])


@router.get("/{team_id}/states", response_model=Envelope[list[WorkflowStateResponse]])
async def list_states(
    team_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    result = await db.execute(
        select(WorkflowState)
        .where(WorkflowState.team_id == team_id)
        .order_by(WorkflowState.type, WorkflowState.position)
    )
    states = result.scalars().all()
    return Envelope(
        data=[WorkflowStateResponse.model_validate(s) for s in states],
        meta=Meta(total=len(states)),
    )


@router.post("/{team_id}/states", response_model=Envelope[WorkflowStateResponse], status_code=201)
async def create_state(
    team_id: uuid.UUID,
    data: WorkflowStateCreate,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    state = WorkflowState(team_id=team_id, **data.model_dump())
    db.add(state)
    await db.commit()
    await db.refresh(state)
    return Envelope(data=WorkflowStateResponse.model_validate(state))
