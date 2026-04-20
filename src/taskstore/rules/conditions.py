"""Evaluate rule conditions against a RuleContext.

Supports: field_equals, field_in, field_is_null, field_not_null,
field_contains (case-insensitive), field_gt, field_lt, field_gte, field_lte,
label_has, and composites: and, or, not.

count_query and estimate_sum require DB access and raise ValueError here;
they are handled by the full evaluator.
"""

from typing import Any

from taskstore.rules.context import RuleContext


def evaluate_condition(condition: dict, ctx: RuleContext) -> bool:
    """Evaluate a single condition node against the context.

    Returns True if the condition is satisfied.
    """
    ctype = condition.get("type")
    if ctype is None:
        raise ValueError(f"Condition missing 'type': {condition}")

    handler = _HANDLERS.get(ctype)
    if handler is None:
        raise ValueError(f"Unknown condition type: {ctype}")
    return handler(condition, ctx)


# ---------- leaf conditions ----------


def _field_equals(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    expected = ctx.resolve_value(cond["value"])
    return field_val == expected


def _field_in(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    values = [ctx.resolve_value(v) for v in cond["values"]]
    return field_val in values


def _field_is_null(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    return field_val is None


def _field_not_null(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    return field_val is not None


def _field_contains(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    if field_val is None:
        return False
    substring = ctx.resolve_value(cond["value"])
    return str(substring).lower() in str(field_val).lower()


def _field_gt(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    value = ctx.resolve_value(cond["value"])
    if field_val is None or value is None:
        return False
    return field_val > value


def _field_lt(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    value = ctx.resolve_value(cond["value"])
    if field_val is None or value is None:
        return False
    return field_val < value


def _field_gte(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    value = ctx.resolve_value(cond["value"])
    if field_val is None or value is None:
        return False
    return field_val >= value


def _field_lte(cond: dict, ctx: RuleContext) -> bool:
    field_val = ctx.resolve_field(cond["field"])
    value = ctx.resolve_value(cond["value"])
    if field_val is None or value is None:
        return False
    return field_val <= value


def _label_has(cond: dict, ctx: RuleContext) -> bool:
    labels = ctx.issue.get("labels", [])
    target = cond["value"]
    # labels can be list of strings or list of dicts with "name"
    for label in labels:
        if isinstance(label, dict):
            if label.get("name") == target:
                return True
        elif label == target:
            return True
    return False


# ---------- composite conditions ----------


def _and(cond: dict, ctx: RuleContext) -> bool:
    conditions = cond.get("conditions", [])
    return all(evaluate_condition(c, ctx) for c in conditions)


def _or(cond: dict, ctx: RuleContext) -> bool:
    conditions = cond.get("conditions", [])
    return any(evaluate_condition(c, ctx) for c in conditions)


def _not(cond: dict, ctx: RuleContext) -> bool:
    inner = cond.get("condition")
    if inner is None:
        raise ValueError("'not' condition requires 'condition' key")
    return not evaluate_condition(inner, ctx)


# ---------- DB-dependent (deferred to evaluator) ----------


def _count_query(cond: dict, ctx: RuleContext) -> bool:
    raise ValueError(
        "count_query conditions require DB access; use the full evaluator"
    )


def _estimate_sum(cond: dict, ctx: RuleContext) -> bool:
    raise ValueError(
        "estimate_sum conditions require DB access; use the full evaluator"
    )


_HANDLERS: dict[str, Any] = {
    "field_equals": _field_equals,
    "field_in": _field_in,
    "field_is_null": _field_is_null,
    "field_not_null": _field_not_null,
    "field_contains": _field_contains,
    "field_gt": _field_gt,
    "field_lt": _field_lt,
    "field_gte": _field_gte,
    "field_lte": _field_lte,
    "label_has": _label_has,
    "and": _and,
    "or": _or,
    "not": _not,
    "count_query": _count_query,
    "estimate_sum": _estimate_sum,
}
