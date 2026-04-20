"""Orchestrates rule evaluation: load matching rules, evaluate conditions,
prepare effects, apply them.

Handles count_query and estimate_sum conditions that need DB access.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.models.comment import Comment
from taskstore.models.enums import RuleTrigger, StateType
from taskstore.models.issue import Issue, IssueLabel
from taskstore.models.label import Label
from taskstore.models.notification import Notification
from taskstore.models.rule import Rule
from taskstore.models.workflow_state import WorkflowState
from taskstore.rules.actions import Effect, prepare_action
from taskstore.rules.conditions import evaluate_condition
from taskstore.rules.context import RuleContext


class RuleRejection(Exception):
    """Raised when a reject action fires."""

    def __init__(self, rule_id: uuid.UUID, rule_name: str, message: str):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.message = message
        super().__init__(message)


async def evaluate_rules(
    db: AsyncSession,
    team_id: uuid.UUID,
    trigger: RuleTrigger,
    ctx: RuleContext,
) -> list[tuple[Rule, list[Effect]]]:
    """Load matching rules and evaluate conditions.

    Returns a list of (rule, effects) tuples for rules whose conditions match.
    Raises RuleRejection if any reject action fires.
    """
    result = await db.execute(
        select(Rule)
        .where(
            Rule.team_id == team_id,
            Rule.enabled.is_(True),
            Rule.trigger == trigger,
        )
        .order_by(Rule.priority.asc())
    )
    rules = list(result.scalars().all())

    matched: list[tuple[Rule, list[Effect]]] = []

    for rule in rules:
        conditions = rule.conditions
        if conditions:
            try:
                cond_result = await _evaluate_condition_with_db(
                    db, conditions, ctx, team_id
                )
            except ValueError:
                continue
            if not cond_result:
                continue

        # Conditions passed — prepare effects
        actions = rule.actions
        if isinstance(actions, dict):
            actions = [actions]

        effects: list[Effect] = []
        for action_def in actions:
            effect = prepare_action(action_def, ctx)
            effects.append(effect)

        # Check for reject effects immediately
        for effect in effects:
            if effect.type == "reject":
                raise RuleRejection(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    message=effect.params["message"],
                )

        matched.append((rule, effects))

    return matched


async def apply_effects(
    db: AsyncSession,
    team_id: uuid.UUID,
    issue: Issue,
    effects: list[tuple[Rule, list[Effect]]],
    user_id: uuid.UUID,
) -> None:
    """Apply non-reject effects to the issue."""
    for rule, effect_list in effects:
        for effect in effect_list:
            if effect.type == "set_field":
                field_name = effect.params["field"]
                value = effect.params["value"]
                setattr(issue, field_name, value)

            elif effect.type == "add_label":
                label_name = effect.params["label_name"]
                # Look up label by name within the team
                label_result = await db.execute(
                    select(Label).where(
                        Label.team_id == team_id,
                        Label.name == label_name,
                    )
                )
                label = label_result.scalar_one_or_none()
                if label:
                    # Check if already attached
                    existing = await db.execute(
                        select(IssueLabel).where(
                            IssueLabel.issue_id == issue.id,
                            IssueLabel.label_id == label.id,
                        )
                    )
                    if existing.scalar_one_or_none() is None:
                        db.add(IssueLabel(issue_id=issue.id, label_id=label.id))

            elif effect.type == "add_comment":
                comment = Comment(
                    issue_id=issue.id,
                    user_id=user_id,
                    body=effect.params["body"],
                )
                db.add(comment)

            elif effect.type == "notify":
                notification = Notification(
                    team_id=team_id,
                    user_id=uuid.UUID(effect.params["user_id"])
                    if effect.params.get("user_id")
                    else None,
                    rule_id=rule.id,
                    issue_id=issue.id,
                    message=effect.params["message"],
                )
                db.add(notification)

    await db.flush()


# ---------- condition evaluation with DB support ----------

_COMPARE_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


async def _evaluate_condition_with_db(
    db: AsyncSession,
    condition: dict,
    ctx: RuleContext,
    team_id: uuid.UUID,
) -> bool:
    """Evaluate a condition, handling DB-dependent types."""
    ctype = condition.get("type")

    if ctype == "count_query":
        return await _eval_count_query(db, condition, ctx, team_id)
    elif ctype == "estimate_sum":
        return await _eval_estimate_sum(db, condition, ctx, team_id)
    elif ctype == "and":
        conditions = condition.get("conditions", [])
        for c in conditions:
            if not await _evaluate_condition_with_db(db, c, ctx, team_id):
                return False
        return True
    elif ctype == "or":
        conditions = condition.get("conditions", [])
        for c in conditions:
            if await _evaluate_condition_with_db(db, c, ctx, team_id):
                return True
        return False
    elif ctype == "not":
        inner = condition.get("condition")
        if inner is None:
            raise ValueError("'not' condition requires 'condition' key")
        return not await _evaluate_condition_with_db(db, inner, ctx, team_id)
    else:
        # Use the synchronous evaluator for non-DB conditions
        return evaluate_condition(condition, ctx)


async def _build_query_filters(
    where: dict, ctx: RuleContext, team_id: uuid.UUID
) -> list:
    """Build SQLAlchemy filter expressions from a where clause."""
    filters: list[Any] = [Issue.team_id == team_id]

    if "state_type" in where:
        st = where["state_type"]
        if isinstance(st, str):
            st = [st]
        state_types = [StateType(s) for s in st]
        subq = select(WorkflowState.id).where(
            WorkflowState.team_id == team_id,
            WorkflowState.type.in_(state_types),
        )
        filters.append(Issue.state_id.in_(subq))

    if "state_type_not_in" in where:
        excluded = where["state_type_not_in"]
        if isinstance(excluded, str):
            excluded = [excluded]
        excluded_types = [StateType(s) for s in excluded]
        excl_subq = select(WorkflowState.id).where(
            WorkflowState.team_id == team_id,
            WorkflowState.type.in_(excluded_types),
        )
        filters.append(Issue.state_id.notin_(excl_subq))

    if "assignee" in where:
        assignee_val = ctx.resolve_value(where["assignee"])
        if assignee_val:
            filters.append(Issue.assignee_id == uuid.UUID(str(assignee_val)))

    if "project_id" in where:
        proj_val = ctx.resolve_value(where["project_id"])
        if proj_val:
            filters.append(Issue.project_id == uuid.UUID(str(proj_val)))

    if "parent_id" in where:
        parent_val = ctx.resolve_value(where["parent_id"])
        if parent_val:
            filters.append(Issue.parent_id == uuid.UUID(str(parent_val)))

    return filters


async def _eval_count_query(
    db: AsyncSession,
    condition: dict,
    ctx: RuleContext,
    team_id: uuid.UUID,
) -> bool:
    where = condition.get("where", {})
    filters = await _build_query_filters(where, ctx, team_id)

    query = select(func.count()).select_from(Issue).where(and_(*filters))
    result = await db.execute(query)
    count = result.scalar_one()

    op = condition.get("operator", ">=")
    value = condition.get("value", 0)
    compare = _COMPARE_OPS.get(op)
    if compare is None:
        raise ValueError(f"Unknown operator: {op}")
    return compare(count, value)


async def _eval_estimate_sum(
    db: AsyncSession,
    condition: dict,
    ctx: RuleContext,
    team_id: uuid.UUID,
) -> bool:
    where = condition.get("where", {})
    filters = await _build_query_filters(where, ctx, team_id)

    query = (
        select(func.coalesce(func.sum(Issue.estimate), 0))
        .select_from(Issue)
        .where(and_(*filters))
    )
    result = await db.execute(query)
    total = result.scalar_one()

    op = condition.get("operator", ">=")
    value = condition.get("value", 0)
    compare = _COMPARE_OPS.get(op)
    if compare is None:
        raise ValueError(f"Unknown operator: {op}")
    return compare(total, value)
