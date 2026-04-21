"""Prepare action effects from rule action definitions.

Actions: reject, set_field, add_label, add_comment, notify.
Messages support template variables: {title}, {priority}, {assignee}, {state}, {project}.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from taskstore.rules.context import RuleContext

# Placeholder pattern compiled once. re.sub is single-pass — user-
# provided field values that happen to contain "{other_placeholder}"
# are NOT re-expanded, unlike the previous chained str.replace.
_TEMPLATE_RE = re.compile(r"\{(\w+)\}")

# Fields that `set_field` actions are allowed to modify on an Issue.
# Anything not in this set would let a rule author escalate privileges
# (e.g. team_id -> cross-tenant move, created_by -> audit forgery,
# archived_at -> hide/unhide, id -> row corruption).
SET_FIELD_ALLOWED = frozenset({
    "priority",
    "estimate",
    "assignee_id",
    "project_id",
    "due_date",
    "state_id",
})


def validate_actions(actions: list[dict]) -> None:
    """Validate a list of action definitions at rule-write time.

    Raises ValueError with a human-readable message if any action is
    structurally invalid or attempts a forbidden mutation.
    """
    if not isinstance(actions, list):
        raise ValueError("actions must be a list")
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError(f"action[{idx}] must be an object")
        atype = action.get("type")
        if atype not in _ACTION_HANDLERS:
            raise ValueError(
                f"action[{idx}] has unknown type: {atype!r}. "
                f"Allowed: {sorted(_ACTION_HANDLERS)}"
            )
        if atype == "set_field":
            fname = action.get("field")
            if fname not in SET_FIELD_ALLOWED:
                raise ValueError(
                    f"action[{idx}] set_field target {fname!r} is not allowed. "
                    f"Allowed fields: {sorted(SET_FIELD_ALLOWED)}"
                )


@dataclass
class Effect:
    """A prepared effect ready to be applied."""
    type: str
    params: dict[str, Any] = field(default_factory=dict)


def _render_template(template: str, ctx: RuleContext) -> str:
    """Replace template variables with values from context.

    Single-pass regex substitution: values that happen to contain
    strings like ``{priority}`` are NOT re-expanded. Unknown
    placeholders pass through unchanged.
    """
    replacements = {
        "title": str(ctx.issue.get("title", "")),
        "priority": str(ctx.issue.get("priority", "")),
        "assignee": str(ctx.issue.get("assignee_id", "")),
        "state": ctx.to_state or ctx.issue.get("state", ""),
        "project": str(ctx.issue.get("project_id", "")),
    }
    return _TEMPLATE_RE.sub(
        lambda m: replacements.get(m.group(1), m.group(0)),
        template,
    )


def prepare_action(action: dict, ctx: RuleContext) -> Effect:
    """Convert an action definition dict to an Effect."""
    action_type = action.get("type")
    if action_type is None:
        raise ValueError(f"Action missing 'type': {action}")

    handler = _ACTION_HANDLERS.get(action_type)
    if handler is None:
        raise ValueError(f"Unknown action type: {action_type}")
    return handler(action, ctx)


def _reject(action: dict, ctx: RuleContext) -> Effect:
    message = action.get("message", "Operation rejected by rule")
    message = _render_template(message, ctx)
    return Effect(type="reject", params={"message": message})


def _set_field(action: dict, ctx: RuleContext) -> Effect:
    return Effect(
        type="set_field",
        params={"field": action["field"], "value": ctx.resolve_value(action["value"])},
    )


def _add_label(action: dict, ctx: RuleContext) -> Effect:
    return Effect(type="add_label", params={"label_name": action["label"]})


def _add_comment(action: dict, ctx: RuleContext) -> Effect:
    body = _render_template(action["body"], ctx)
    return Effect(type="add_comment", params={"body": body})


def _notify(action: dict, ctx: RuleContext) -> Effect:
    message = _render_template(action["message"], ctx)
    user_id = ctx.resolve_value(action.get("user_id"))
    return Effect(type="notify", params={"message": message, "user_id": user_id})


_ACTION_HANDLERS = {
    "reject": _reject,
    "set_field": _set_field,
    "add_label": _add_label,
    "add_comment": _add_comment,
    "notify": _notify,
}
