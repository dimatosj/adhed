import uuid
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import compute_diff, record_audit
from taskstore.engine.transitions import is_valid_transition
from taskstore.models.enums import AuditAction, IssueType, ProjectState, RuleTrigger, StateType
from taskstore.models.issue import Issue, IssueLabel
from taskstore.models.label import Label
from taskstore.models.project import Project
from taskstore.models.team import Team
from taskstore.models.user import TeamMembership
from taskstore.models.workflow_state import WorkflowState
from taskstore.rules.context import RuleContext
from taskstore.rules.evaluator import (
    RuleEvaluationError,
    RuleRejection,
    apply_effects,
    evaluate_rules,
)
from taskstore.schemas.common import Envelope, ErrorDetail
from taskstore.schemas.issue import IssueCreate, IssueResponse, IssueStateInfo, IssueLabelInfo, IssueUpdate


async def _validate_references(
    db: AsyncSession,
    team_id: uuid.UUID,
    *,
    state_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    parent_id: uuid.UUID | None = None,
    label_ids: list[uuid.UUID] | None = None,
    assignee_id: uuid.UUID | None = None,
) -> None:
    """Verify every FK on an Issue write belongs to the authed team.

    FK constraints in Postgres are global (e.g. project_id references
    projects.id with no team scoping), so without this check an API-key
    holder for team A could reference team B's resources. Each non-None
    argument is resolved and its team_id compared.

    Raises HTTPException(422) on any mismatch. Callers should invoke
    this before creating/updating an Issue.
    """
    if state_id is not None:
        row = await db.execute(
            select(WorkflowState.team_id).where(WorkflowState.id == state_id)
        )
        owner = row.scalar_one_or_none()
        if owner is None or owner != team_id:
            raise HTTPException(status_code=422, detail="state_id is not in this team")

    if project_id is not None:
        row = await db.execute(
            select(Project.team_id).where(Project.id == project_id)
        )
        owner = row.scalar_one_or_none()
        if owner is None or owner != team_id:
            raise HTTPException(status_code=422, detail="project_id is not in this team")

    if parent_id is not None:
        row = await db.execute(
            select(Issue.team_id).where(Issue.id == parent_id)
        )
        owner = row.scalar_one_or_none()
        if owner is None or owner != team_id:
            raise HTTPException(status_code=422, detail="parent_id is not in this team")

    if label_ids:
        row = await db.execute(
            select(func.count()).select_from(Label).where(
                Label.id.in_(label_ids), Label.team_id == team_id
            )
        )
        found = row.scalar_one()
        if found != len(set(label_ids)):
            raise HTTPException(status_code=422, detail="one or more label_ids are not in this team")

    if assignee_id is not None:
        row = await db.execute(
            select(TeamMembership.user_id).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == assignee_id,
            )
        )
        if row.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="assignee_id is not a member of this team")


async def _resolve_default_state(db: AsyncSession, team: Team) -> uuid.UUID:
    """Pick the default state for a new issue based on team triage settings."""
    settings = team.settings or {}
    triage_enabled = settings.get("triage_enabled", True)

    if triage_enabled:
        result = await db.execute(
            select(WorkflowState)
            .where(WorkflowState.team_id == team.id, WorkflowState.type == StateType.TRIAGE)
            .order_by(WorkflowState.position)
            .limit(1)
        )
        state = result.scalar_one_or_none()
        if state:
            return state.id

    # Fallback to first backlog state
    result = await db.execute(
        select(WorkflowState)
        .where(WorkflowState.team_id == team.id, WorkflowState.type == StateType.BACKLOG)
        .order_by(WorkflowState.position)
        .limit(1)
    )
    state = result.scalar_one_or_none()
    if state:
        return state.id

    raise HTTPException(status_code=500, detail="No default state available for this team")


async def _build_response(db: AsyncSession, issue: Issue) -> IssueResponse:
    """Build an IssueResponse with state info and labels."""
    # Load state
    result = await db.execute(
        select(WorkflowState).where(WorkflowState.id == issue.state_id)
    )
    state = result.scalar_one()

    # Load labels
    result = await db.execute(
        select(Label)
        .join(IssueLabel, IssueLabel.label_id == Label.id)
        .where(IssueLabel.issue_id == issue.id)
        .order_by(Label.name)
    )
    labels = list(result.scalars().all())

    return IssueResponse(
        id=issue.id,
        team_id=issue.team_id,
        title=issue.title,
        description=issue.description,
        type=issue.type,
        priority=issue.priority,
        estimate=issue.estimate,
        state=IssueStateInfo.model_validate(state),
        assignee_id=issue.assignee_id,
        project_id=issue.project_id,
        parent_id=issue.parent_id,
        due_date=issue.due_date,
        custom_fields=issue.custom_fields,
        created_by=str(issue.created_by),
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        archived_at=issue.archived_at,
        labels=[IssueLabelInfo.model_validate(l) for l in labels],
    )


async def create_issue(
    db: AsyncSession,
    team: Team,
    data: IssueCreate,
    user_id: uuid.UUID,
) -> IssueResponse:
    state_id = data.state_id
    if state_id is None:
        state_id = await _resolve_default_state(db, team)
    else:
        await _validate_references(db, team.id, state_id=state_id)
    await _validate_references(
        db,
        team.id,
        project_id=data.project_id,
        parent_id=data.parent_id,
        label_ids=data.label_ids,
        assignee_id=data.assignee_id,
    )

    issue = Issue(
        team_id=team.id,
        title=data.title,
        description=data.description,
        type=data.type,
        priority=data.priority,
        estimate=data.estimate,
        state_id=state_id,
        assignee_id=data.assignee_id,
        project_id=data.project_id,
        parent_id=data.parent_id,
        due_date=data.due_date,
        custom_fields=data.custom_fields,
        created_by=user_id,
    )
    db.add(issue)
    await db.flush()

    # Attach labels
    if data.label_ids:
        for label_id in data.label_ids:
            db.add(IssueLabel(issue_id=issue.id, label_id=label_id))
        await db.flush()

    # Load state for rule context
    state_result = await db.execute(
        select(WorkflowState).where(WorkflowState.id == state_id)
    )
    state = state_result.scalar_one()

    # Build rule context from the newly created issue
    ctx = RuleContext(
        issue={
            "title": issue.title,
            "description": issue.description,
            "type": issue.type.value if issue.type else None,
            "priority": issue.priority,
            "estimate": issue.estimate,
            "assignee_id": str(issue.assignee_id) if issue.assignee_id else None,
            "project_id": str(issue.project_id) if issue.project_id else None,
            "parent_id": str(issue.parent_id) if issue.parent_id else None,
            "state": state.name,
            "state_type": state.type.value,
            "labels": [],
        },
        current_user=str(user_id),
        to_state=state.name,
        to_state_type=state.type.value,
    )

    # Evaluate rules for ISSUE_CREATED
    try:
        effects = await evaluate_rules(db, team.id, RuleTrigger.ISSUE_CREATED, ctx)
    except (RuleRejection, RuleEvaluationError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail=Envelope(
                errors=[ErrorDetail(
                    rule_id=str(exc.rule_id),
                    rule_name=exc.rule_name,
                    message=exc.message,
                )],
            ).model_dump(),
        )

    # Apply non-reject effects
    if effects:
        await apply_effects(db, team.id, issue, effects, user_id)

    await record_audit(db, team.id, "issue", issue.id, AuditAction.CREATE, user_id)
    await db.commit()
    await db.refresh(issue)
    return await _build_response(db, issue)


async def get_issue(db: AsyncSession, issue_id: uuid.UUID) -> IssueResponse:
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return await _build_response(db, issue)


async def get_issue_raw(db: AsyncSession, issue_id: uuid.UUID) -> Issue:
    """Get the raw Issue model (for auth checks)."""
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


async def update_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
    data: IssueUpdate,
    user_id: uuid.UUID | None = None,
) -> IssueResponse:
    issue = await get_issue_raw(db, issue_id)

    update_data = data.model_dump(exclude_unset=True)

    # Cross-tenant reference validation — only check fields being changed.
    await _validate_references(
        db,
        issue.team_id,
        state_id=update_data.get("state_id"),
        project_id=update_data.get("project_id"),
        assignee_id=update_data.get("assignee_id"),
    )

    old_state = None
    new_state = None

    # State transition validation
    if "state_id" in update_data and update_data["state_id"] != issue.state_id:
        old_state_result = await db.execute(
            select(WorkflowState).where(WorkflowState.id == issue.state_id)
        )
        old_state = old_state_result.scalar_one()

        new_state_result = await db.execute(
            select(WorkflowState).where(WorkflowState.id == update_data["state_id"])
        )
        new_state = new_state_result.scalar_one_or_none()
        if not new_state:
            raise HTTPException(status_code=422, detail="Target state not found")

        if not is_valid_transition(old_state.type, new_state.type):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid state transition: {old_state.type} -> {new_state.type}",
            )

    # Capture old values for diff before mutating
    TRACKED_FIELDS = ["title", "description", "priority", "estimate", "state_id",
                      "assignee_id", "project_id", "due_date", "type", "custom_fields"]
    old_values = {f: getattr(issue, f) for f in TRACKED_FIELDS}
    # Normalise UUIDs to strings so compute_diff can compare them
    old_values_str = {
        k: str(v) if isinstance(v, uuid.UUID) else v
        for k, v in old_values.items()
    }

    old_assignee = issue.assignee_id

    # --- Rule evaluation (PRE-COMMIT: before mutation is applied) ---
    # Build context from the CURRENT issue state (pre-mutation)
    if old_state is None:
        cur_state_result = await db.execute(
            select(WorkflowState).where(WorkflowState.id == issue.state_id)
        )
        cur_state = cur_state_result.scalar_one()
    else:
        cur_state = old_state

    ctx = RuleContext(
        issue={
            "title": issue.title,
            "description": issue.description,
            "type": issue.type.value if issue.type else None,
            "priority": issue.priority,
            "estimate": issue.estimate,
            "assignee_id": str(issue.assignee_id) if issue.assignee_id else None,
            "project_id": str(issue.project_id) if issue.project_id else None,
            "parent_id": str(issue.parent_id) if issue.parent_id else None,
            "state": cur_state.name,
            "state_type": cur_state.type.value,
        },
        current_user=str(user_id) if user_id else "",
        from_state=cur_state.name if old_state else "",
        from_state_type=cur_state.type.value if old_state else "",
        to_state=new_state.name if new_state else "",
        to_state_type=new_state.type.value if new_state else "",
        old_assignee=str(old_assignee) if old_assignee else None,
        new_assignee=str(update_data["assignee_id"]) if "assignee_id" in update_data else None,
        changed_fields=list(update_data.keys()),
    )

    all_effects: list[tuple] = []

    try:
        # State change trigger
        if old_state is not None and new_state is not None:
            effects = await evaluate_rules(
                db, issue.team_id, RuleTrigger.ISSUE_STATE_CHANGED, ctx
            )
            all_effects.extend(effects)

        # Assignee change trigger
        if "assignee_id" in update_data and update_data["assignee_id"] != old_assignee:
            effects = await evaluate_rules(
                db, issue.team_id, RuleTrigger.ISSUE_ASSIGNED, ctx
            )
            all_effects.extend(effects)

        # General update trigger
        effects = await evaluate_rules(
            db, issue.team_id, RuleTrigger.ISSUE_UPDATED, ctx
        )
        all_effects.extend(effects)

    except (RuleRejection, RuleEvaluationError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail=Envelope(
                errors=[ErrorDetail(
                    rule_id=str(exc.rule_id),
                    rule_name=exc.rule_name,
                    message=exc.message,
                )],
            ).model_dump(),
        )

    # --- Now apply the mutation ---
    for field, value in update_data.items():
        setattr(issue, field, value)

    # Compute diff using string-normalised new values
    new_values_str = {
        k: str(update_data[k]) if isinstance(update_data.get(k), uuid.UUID) else update_data.get(k, old_values_str[k])
        for k in TRACKED_FIELDS
    }
    diff = compute_diff(old_values_str, new_values_str, TRACKED_FIELDS)

    await db.flush()

    # Apply rule effects after mutation
    if all_effects:
        await apply_effects(db, issue.team_id, issue, all_effects, user_id or issue.created_by)

    if user_id is not None:
        await record_audit(db, issue.team_id, "issue", issue.id, AuditAction.UPDATE, user_id, diff)

    await db.commit()
    await db.refresh(issue)
    return await _build_response(db, issue)


async def delete_issue(db: AsyncSession, issue_id: uuid.UUID) -> None:
    issue = await get_issue_raw(db, issue_id)

    # Check for active children (non-completed, non-canceled)
    result = await db.execute(
        select(func.count())
        .select_from(Issue)
        .join(WorkflowState, Issue.state_id == WorkflowState.id)
        .where(
            Issue.parent_id == issue_id,
            WorkflowState.type.notin_([StateType.COMPLETED, StateType.CANCELED]),
        )
    )
    active_children = result.scalar_one()
    if active_children > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete issue with active subtasks",
        )

    await db.delete(issue)
    await db.commit()


async def list_issues(
    db: AsyncSession,
    team_id: uuid.UUID,
    *,
    state_type: str | None = None,
    assignee: uuid.UUID | None = None,
    project_id: str | None = None,
    parent_id: str | None = None,
    label: str | None = None,
    priority: str | None = None,
    type: str | None = None,
    created_by: uuid.UUID | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    overdue: bool | None = None,
    title_search: str | None = None,
    estimate_lte: int | None = None,
    estimate_gte: int | None = None,
    archived: bool = False,
    limit: int = 50,
    offset: int = 0,
    sort: str = "created_at",
    order: str = "desc",
) -> tuple[list[IssueResponse], int]:
    # Clamp limit
    if limit > 200:
        limit = 200

    # Base query
    query = select(Issue).where(Issue.team_id == team_id)
    count_query = select(func.count()).select_from(Issue).where(Issue.team_id == team_id)

    filters = []

    # Archived filter
    if not archived:
        filters.append(Issue.archived_at.is_(None))

    # State type filter
    if state_type:
        type_values = [StateType(t.strip()) for t in state_type.split(",")]
        state_type_subq = (
            select(WorkflowState.id)
            .where(
                WorkflowState.team_id == team_id,
                WorkflowState.type.in_(type_values),
            )
        )
        filters.append(Issue.state_id.in_(state_type_subq))

    # Assignee
    if assignee is not None:
        filters.append(Issue.assignee_id == assignee)

    # Project ID (supports "null" for unprojecte)
    if project_id is not None:
        if project_id == "null":
            filters.append(Issue.project_id.is_(None))
        else:
            filters.append(Issue.project_id == uuid.UUID(project_id))

    # Parent ID (supports "null" for top-level)
    if parent_id is not None:
        if parent_id == "null":
            filters.append(Issue.parent_id.is_(None))
        else:
            filters.append(Issue.parent_id == uuid.UUID(parent_id))

    # Label filter (AND logic — issue must have ALL specified labels)
    if label:
        label_names = [n.strip() for n in label.split(",")]
        for label_name in label_names:
            label_subq = (
                select(IssueLabel.issue_id)
                .join(Label, IssueLabel.label_id == Label.id)
                .where(Label.team_id == team_id, Label.name == label_name)
            )
            filters.append(Issue.id.in_(label_subq))

    # Priority
    if priority is not None:
        prio_values = [int(p.strip()) for p in priority.split(",")]
        filters.append(Issue.priority.in_(prio_values))

    # Type
    if type is not None:
        filters.append(Issue.type == IssueType(type))

    # Created by
    if created_by is not None:
        filters.append(Issue.created_by == created_by)

    # Due date filters
    if due_before is not None:
        filters.append(Issue.due_date < due_before)

    if due_after is not None:
        filters.append(Issue.due_date > due_after)

    # Overdue sugar
    if overdue:
        today = date.today()
        filters.append(Issue.due_date < today)
        non_terminal_subq = (
            select(WorkflowState.id)
            .where(
                WorkflowState.team_id == team_id,
                WorkflowState.type.notin_([StateType.COMPLETED, StateType.CANCELED]),
            )
        )
        filters.append(Issue.state_id.in_(non_terminal_subq))

    # Full-text search
    if title_search:
        ts_query = func.plainto_tsquery("english", title_search)
        filters.append(Issue.title_search.op("@@")(ts_query))

    # Estimate filters
    if estimate_lte is not None:
        filters.append(Issue.estimate <= estimate_lte)
    if estimate_gte is not None:
        filters.append(Issue.estimate >= estimate_gte)

    # Apply all filters
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Sort
    allowed_sorts = {"created_at", "updated_at", "priority", "due_date"}
    sort_col = sort if sort in allowed_sorts else "created_at"
    col = getattr(Issue, sort_col)
    if order == "asc":
        query = query.order_by(col.asc())
    else:
        query = query.order_by(col.desc())

    # Pagination
    query = query.offset(offset).limit(limit)

    # Execute
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query)
    issues = list(result.scalars().all())

    responses = [await _build_response(db, issue) for issue in issues]
    return responses, total


async def batch_create_issues(
    db: AsyncSession,
    team: Team,
    items: list[IssueCreate],
    user_id: uuid.UUID,
) -> list[dict]:
    """Create multiple issues. Rules fire per item. Rejected items include
    error in the response but don't fail the whole batch."""
    results: list[dict] = []
    for data in items:
        # Each item is created in its own savepoint so a rejection
        # doesn't roll back previously created issues.
        try:
            async with db.begin_nested():
                response = await _create_issue_inner(db, team, data, user_id)
            results.append({"data": response, "error": None})
        except HTTPException as exc:
            # Extract error message from the HTTPException detail
            detail = exc.detail
            if isinstance(detail, dict) and "errors" in detail:
                msg = detail["errors"][0]["message"]
            else:
                msg = str(detail)
            results.append({"data": None, "error": msg})
    await db.commit()
    return results


async def _create_issue_inner(
    db: AsyncSession,
    team: Team,
    data: IssueCreate,
    user_id: uuid.UUID,
) -> IssueResponse:
    """Core create logic shared by create_issue and batch_create_issues.
    Does NOT commit — caller is responsible for committing."""
    state_id = data.state_id
    if state_id is None:
        state_id = await _resolve_default_state(db, team)
    else:
        await _validate_references(db, team.id, state_id=state_id)
    await _validate_references(
        db,
        team.id,
        project_id=data.project_id,
        parent_id=data.parent_id,
        label_ids=data.label_ids,
        assignee_id=data.assignee_id,
    )

    issue = Issue(
        team_id=team.id,
        title=data.title,
        description=data.description,
        type=data.type,
        priority=data.priority,
        estimate=data.estimate,
        state_id=state_id,
        assignee_id=data.assignee_id,
        project_id=data.project_id,
        parent_id=data.parent_id,
        due_date=data.due_date,
        custom_fields=data.custom_fields,
        created_by=user_id,
    )
    db.add(issue)
    await db.flush()

    # Attach labels
    if data.label_ids:
        for label_id in data.label_ids:
            db.add(IssueLabel(issue_id=issue.id, label_id=label_id))
        await db.flush()

    # Load state for rule context
    state_result = await db.execute(
        select(WorkflowState).where(WorkflowState.id == state_id)
    )
    state = state_result.scalar_one()

    # Build rule context
    ctx = RuleContext(
        issue={
            "title": issue.title,
            "description": issue.description,
            "type": issue.type.value if issue.type else None,
            "priority": issue.priority,
            "estimate": issue.estimate,
            "assignee_id": str(issue.assignee_id) if issue.assignee_id else None,
            "project_id": str(issue.project_id) if issue.project_id else None,
            "parent_id": str(issue.parent_id) if issue.parent_id else None,
            "state": state.name,
            "state_type": state.type.value,
            "labels": [],
        },
        current_user=str(user_id),
        to_state=state.name,
        to_state_type=state.type.value,
    )

    # Evaluate rules for ISSUE_CREATED
    try:
        effects = await evaluate_rules(db, team.id, RuleTrigger.ISSUE_CREATED, ctx)
    except (RuleRejection, RuleEvaluationError) as exc:
        raise HTTPException(
            status_code=422,
            detail=Envelope(
                errors=[ErrorDetail(
                    rule_id=str(exc.rule_id),
                    rule_name=exc.rule_name,
                    message=exc.message,
                )],
            ).model_dump(),
        )

    # Apply non-reject effects
    if effects:
        await apply_effects(db, team.id, issue, effects, user_id)

    await record_audit(db, team.id, "issue", issue.id, AuditAction.CREATE, user_id)
    await db.flush()
    await db.refresh(issue)
    return await _build_response(db, issue)


async def batch_update_issues(
    db: AsyncSession,
    team_id: uuid.UUID,
    filter_params: dict,
    update_data: dict,
    user_id: uuid.UUID | None = None,
) -> list[IssueResponse]:
    """Apply an update to all issues matching the filter."""
    # Build filter query
    query = select(Issue).where(Issue.team_id == team_id)

    if "state_type" in filter_params:
        state_type_val = filter_params["state_type"]
        type_values = [StateType(t.strip()) for t in state_type_val.split(",")]
        state_type_subq = (
            select(WorkflowState.id)
            .where(
                WorkflowState.team_id == team_id,
                WorkflowState.type.in_(type_values),
            )
        )
        query = query.where(Issue.state_id.in_(state_type_subq))

    if "assignee_id" in filter_params:
        query = query.where(Issue.assignee_id == uuid.UUID(filter_params["assignee_id"]))

    if "project_id" in filter_params:
        query = query.where(Issue.project_id == uuid.UUID(filter_params["project_id"]))

    if "priority" in filter_params:
        query = query.where(Issue.priority == filter_params["priority"])

    result = await db.execute(query)
    issues = list(result.scalars().all())

    update_schema = IssueUpdate(**update_data)
    responses = []
    for issue in issues:
        resp = await update_issue(db, issue.id, update_schema, user_id=user_id)
        responses.append(resp)

    return responses


async def convert_to_project(
    db: AsyncSession,
    issue_id: uuid.UUID,
) -> dict:
    """Convert an issue into a project. Creates a new project with the
    issue's name and description, then assigns the issue to the new project."""
    issue = await get_issue_raw(db, issue_id)

    project = Project(
        team_id=issue.team_id,
        name=issue.title,
        description=issue.description,
        state=ProjectState.PLANNED,
    )
    db.add(project)
    await db.flush()

    issue.project_id = project.id
    await db.commit()
    await db.refresh(issue)
    await db.refresh(project)

    from taskstore.schemas.project import ProjectResponse
    project_response = ProjectResponse(
        id=project.id,
        team_id=project.team_id,
        name=project.name,
        description=project.description,
        state=project.state,
        lead_id=project.lead_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
    issue_response = await _build_response(db, issue)

    return {"project": project_response, "issue": issue_response}
