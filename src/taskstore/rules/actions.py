"""Prepare action effects from rule action definitions.

Actions: reject, set_field, add_label, add_comment, notify.
Messages support template variables: {title}, {priority}, {assignee}, {state}, {project}.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taskstore.rules.context import RuleContext


@dataclass
class Effect:
    """A prepared effect ready to be applied."""
    type: str
    params: dict[str, Any] = field(default_factory=dict)


def _render_template(template: str, ctx: RuleContext) -> str:
    """Replace template variables with values from context."""
    replacements = {
        "title": ctx.issue.get("title", ""),
        "priority": str(ctx.issue.get("priority", "")),
        "assignee": str(ctx.issue.get("assignee_id", "")),
        "state": ctx.to_state or ctx.issue.get("state", ""),
        "project": str(ctx.issue.get("project_id", "")),
    }
    result = template
    for key, value in replacements.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


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
