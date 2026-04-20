import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.models.enums import StateType
from taskstore.models.workflow_state import WorkflowState

DEFAULT_STATES = [
    {"name": "Triage", "type": StateType.TRIAGE, "position": 0},
    {"name": "Backlog", "type": StateType.BACKLOG, "position": 0},
    {"name": "Todo", "type": StateType.UNSTARTED, "position": 0},
    {"name": "In Progress", "type": StateType.STARTED, "position": 0},
    {"name": "Done", "type": StateType.COMPLETED, "position": 0},
    {"name": "Canceled", "type": StateType.CANCELED, "position": 0},
]


async def seed_default_states(db: AsyncSession, team_id: uuid.UUID) -> list[WorkflowState]:
    states = []
    for s in DEFAULT_STATES:
        state = WorkflowState(team_id=team_id, **s)
        db.add(state)
        states.append(state)
    await db.flush()
    return states
