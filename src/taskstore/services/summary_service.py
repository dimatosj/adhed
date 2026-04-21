import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.models.enums import ProjectState, StateType
from taskstore.models.issue import Issue
from taskstore.models.project import Project
from taskstore.models.workflow_state import WorkflowState
from taskstore.schemas.summary import (
    DueSoonItem,
    OverdueItem,
    RecentlyCompleted,
    StalledProject,
    SummaryData,
    WaitingForItem,
)
from taskstore.utils.time import now_utc


async def get_summary(
    db: AsyncSession,
    team_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> SummaryData:
    today = date.today()
    now = now_utc()
    seven_days_ago = now - timedelta(days=7)
    seven_days_from_now = today + timedelta(days=7)

    # State type mapping: state_id -> state_type
    state_result = await db.execute(
        select(WorkflowState).where(WorkflowState.team_id == team_id)
    )
    states = list(state_result.scalars().all())
    state_ids_by_type: dict[StateType, list[uuid.UUID]] = {}
    for s in states:
        state_ids_by_type.setdefault(s.type, []).append(s.id)

    # --- triage_count ---
    triage_ids = state_ids_by_type.get(StateType.TRIAGE, [])
    triage_count = 0
    if triage_ids:
        result = await db.execute(
            select(func.count())
            .select_from(Issue)
            .where(Issue.team_id == team_id, Issue.state_id.in_(triage_ids))
        )
        triage_count = result.scalar_one()

    # --- by_state_type ---
    result = await db.execute(
        select(WorkflowState.type, func.count(Issue.id))
        .join(WorkflowState, Issue.state_id == WorkflowState.id)
        .where(Issue.team_id == team_id)
        .group_by(WorkflowState.type)
    )
    by_state_type = {row[0].value: row[1] for row in result.all()}

    # --- overdue ---
    non_terminal_ids = []
    for st in [StateType.TRIAGE, StateType.BACKLOG, StateType.UNSTARTED, StateType.STARTED]:
        non_terminal_ids.extend(state_ids_by_type.get(st, []))

    overdue_items = []
    if non_terminal_ids:
        result = await db.execute(
            select(Issue).where(
                Issue.team_id == team_id,
                Issue.due_date < today,
                Issue.state_id.in_(non_terminal_ids),
            )
        )
        for issue in result.scalars().all():
            days = (today - issue.due_date).days
            overdue_items.append(OverdueItem(
                id=issue.id,
                title=issue.title,
                due_date=issue.due_date,
                days_overdue=days,
            ))

    # --- due_soon (within 7 days, not completed/canceled) ---
    due_soon_items = []
    if non_terminal_ids:
        result = await db.execute(
            select(Issue).where(
                Issue.team_id == team_id,
                Issue.due_date >= today,
                Issue.due_date <= seven_days_from_now,
                Issue.state_id.in_(non_terminal_ids),
            )
        )
        for issue in result.scalars().all():
            days = (issue.due_date - today).days
            due_soon_items.append(DueSoonItem(
                id=issue.id,
                title=issue.title,
                due_date=issue.due_date,
                days_until=days,
            ))

    # --- by_assignee ---
    result = await db.execute(
        select(Issue.assignee_id, WorkflowState.type, func.count(Issue.id))
        .join(WorkflowState, Issue.state_id == WorkflowState.id)
        .where(Issue.team_id == team_id, Issue.assignee_id.isnot(None))
        .group_by(Issue.assignee_id, WorkflowState.type)
    )
    by_assignee: dict[str, dict[str, int]] = {}
    for row in result.all():
        assignee_str = str(row[0])
        state_type_val = row[1].value
        count = row[2]
        if assignee_str not in by_assignee:
            by_assignee[assignee_str] = {}
        by_assignee[assignee_str][state_type_val] = count

    # Add overdue counts per assignee
    if non_terminal_ids:
        result = await db.execute(
            select(Issue.assignee_id, func.count(Issue.id))
            .where(
                Issue.team_id == team_id,
                Issue.assignee_id.isnot(None),
                Issue.due_date < today,
                Issue.state_id.in_(non_terminal_ids),
            )
            .group_by(Issue.assignee_id)
        )
        for row in result.all():
            assignee_str = str(row[0])
            if assignee_str not in by_assignee:
                by_assignee[assignee_str] = {}
            by_assignee[assignee_str]["overdue"] = row[1]

    # --- recently_completed (last 7 days) ---
    completed_ids = state_ids_by_type.get(StateType.COMPLETED, [])
    recently_completed = []
    if completed_ids:
        result = await db.execute(
            select(Issue).where(
                Issue.team_id == team_id,
                Issue.state_id.in_(completed_ids),
                Issue.updated_at >= seven_days_ago,
            ).order_by(Issue.updated_at.desc())
        )
        for issue in result.scalars().all():
            recently_completed.append(RecentlyCompleted(
                id=issue.id,
                title=issue.title,
                completed_at=issue.updated_at,
            ))

    # --- stalled_projects ---
    # Projects with state=started and zero issues in unstarted or started
    active_issue_types = [StateType.UNSTARTED, StateType.STARTED]
    active_state_ids = []
    for st in active_issue_types:
        active_state_ids.extend(state_ids_by_type.get(st, []))

    stalled_projects = []
    result = await db.execute(
        select(Project).where(
            Project.team_id == team_id,
            Project.state == ProjectState.STARTED,
        )
    )
    for project in result.scalars().all():
        # Count unstarted+started issues
        active_count_result = await db.execute(
            select(func.count()).select_from(Issue).where(
                Issue.project_id == project.id,
                Issue.state_id.in_(active_state_ids) if active_state_ids else Issue.id.is_(None),
            )
        )
        active_count = active_count_result.scalar_one()
        if active_count == 0:
            # Count backlog issues
            backlog_ids = state_ids_by_type.get(StateType.BACKLOG, [])
            backlog_count = 0
            if backlog_ids:
                bc_result = await db.execute(
                    select(func.count()).select_from(Issue).where(
                        Issue.project_id == project.id,
                        Issue.state_id.in_(backlog_ids),
                    )
                )
                backlog_count = bc_result.scalar_one()

            days_since = (now - project.updated_at).days
            stalled_projects.append(StalledProject(
                id=project.id,
                name=project.name,
                backlog_count=backlog_count,
                days_since_activity=days_since,
            ))

    # --- waiting_for ---
    waiting_for = []
    if user_id is not None:
        waiting_state_types = [StateType.UNSTARTED, StateType.STARTED]
        waiting_state_ids = []
        for st in waiting_state_types:
            waiting_state_ids.extend(state_ids_by_type.get(st, []))

        if waiting_state_ids:
            result = await db.execute(
                select(Issue).where(
                    Issue.team_id == team_id,
                    Issue.created_by == user_id,
                    Issue.assignee_id.isnot(None),
                    Issue.assignee_id != user_id,
                    Issue.state_id.in_(waiting_state_ids),
                )
            )
            for issue in result.scalars().all():
                waiting_for.append(WaitingForItem(
                    id=issue.id,
                    title=issue.title,
                    assignee=str(issue.assignee_id) if issue.assignee_id else None,
                    created_by=str(issue.created_by),
                ))

    return SummaryData(
        triage_count=triage_count,
        overdue=overdue_items,
        due_soon=due_soon_items,
        stalled_projects=stalled_projects,
        by_state_type=by_state_type,
        by_assignee=by_assignee,
        recently_completed=recently_completed,
        waiting_for=waiting_for,
    )
