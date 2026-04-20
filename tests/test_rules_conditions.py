"""Pure unit tests for rule condition evaluation — no DB needed."""

import pytest

from taskstore.rules.conditions import evaluate_condition
from taskstore.rules.context import RuleContext


def _make_ctx(**overrides):
    defaults = {
        "issue": {
            "title": "Fix login bug",
            "priority": 2,
            "assignee_id": "user-1",
            "state_type": "started",
            "labels": ["bug", "urgent"],
        },
        "current_user": "user-1",
        "from_state": "Backlog",
        "from_state_type": "backlog",
        "to_state": "In Progress",
        "to_state_type": "started",
    }
    defaults.update(overrides)
    return RuleContext(**defaults)


# ---------- field_equals ----------


def test_field_equals_match():
    ctx = _make_ctx()
    cond = {"type": "field_equals", "field": "priority", "value": 2}
    assert evaluate_condition(cond, ctx) is True


def test_field_equals_no_match():
    ctx = _make_ctx()
    cond = {"type": "field_equals", "field": "priority", "value": 5}
    assert evaluate_condition(cond, ctx) is False


def test_field_equals_trigger_field():
    ctx = _make_ctx()
    cond = {"type": "field_equals", "field": "from_state_type", "value": "backlog"}
    assert evaluate_condition(cond, ctx) is True


# ---------- field_in ----------


def test_field_in_match():
    ctx = _make_ctx()
    cond = {"type": "field_in", "field": "priority", "values": [1, 2, 3]}
    assert evaluate_condition(cond, ctx) is True


def test_field_in_no_match():
    ctx = _make_ctx()
    cond = {"type": "field_in", "field": "priority", "values": [4, 5]}
    assert evaluate_condition(cond, ctx) is False


# ---------- field_is_null / field_not_null ----------


def test_field_is_null_true():
    ctx = _make_ctx(issue={"title": "x", "description": None})
    cond = {"type": "field_is_null", "field": "description"}
    assert evaluate_condition(cond, ctx) is True


def test_field_is_null_false():
    ctx = _make_ctx()
    cond = {"type": "field_is_null", "field": "title"}
    assert evaluate_condition(cond, ctx) is False


def test_field_not_null():
    ctx = _make_ctx()
    cond = {"type": "field_not_null", "field": "title"}
    assert evaluate_condition(cond, ctx) is True


# ---------- field_contains ----------


def test_field_contains_match():
    ctx = _make_ctx()
    cond = {"type": "field_contains", "field": "title", "value": "login"}
    assert evaluate_condition(cond, ctx) is True


def test_field_contains_case_insensitive():
    ctx = _make_ctx()
    cond = {"type": "field_contains", "field": "title", "value": "LOGIN"}
    assert evaluate_condition(cond, ctx) is True


def test_field_contains_no_match():
    ctx = _make_ctx()
    cond = {"type": "field_contains", "field": "title", "value": "signup"}
    assert evaluate_condition(cond, ctx) is False


# ---------- field_gte ----------


def test_field_gte_match():
    ctx = _make_ctx()
    cond = {"type": "field_gte", "field": "priority", "value": 2}
    assert evaluate_condition(cond, ctx) is True


def test_field_gte_no_match():
    ctx = _make_ctx()
    cond = {"type": "field_gte", "field": "priority", "value": 3}
    assert evaluate_condition(cond, ctx) is False


# ---------- composites ----------


def test_and_all_true():
    ctx = _make_ctx()
    cond = {
        "type": "and",
        "conditions": [
            {"type": "field_equals", "field": "priority", "value": 2},
            {"type": "field_contains", "field": "title", "value": "login"},
        ],
    }
    assert evaluate_condition(cond, ctx) is True


def test_and_one_false():
    ctx = _make_ctx()
    cond = {
        "type": "and",
        "conditions": [
            {"type": "field_equals", "field": "priority", "value": 2},
            {"type": "field_equals", "field": "priority", "value": 5},
        ],
    }
    assert evaluate_condition(cond, ctx) is False


def test_or_one_true():
    ctx = _make_ctx()
    cond = {
        "type": "or",
        "conditions": [
            {"type": "field_equals", "field": "priority", "value": 99},
            {"type": "field_contains", "field": "title", "value": "login"},
        ],
    }
    assert evaluate_condition(cond, ctx) is True


def test_or_all_false():
    ctx = _make_ctx()
    cond = {
        "type": "or",
        "conditions": [
            {"type": "field_equals", "field": "priority", "value": 99},
            {"type": "field_contains", "field": "title", "value": "signup"},
        ],
    }
    assert evaluate_condition(cond, ctx) is False


def test_not_composition():
    ctx = _make_ctx()
    cond = {
        "type": "not",
        "condition": {"type": "field_equals", "field": "priority", "value": 99},
    }
    assert evaluate_condition(cond, ctx) is True


def test_not_composition_false():
    ctx = _make_ctx()
    cond = {
        "type": "not",
        "condition": {"type": "field_equals", "field": "priority", "value": 2},
    }
    assert evaluate_condition(cond, ctx) is False


# ---------- count_query / estimate_sum raise ValueError ----------


def test_count_query_raises():
    ctx = _make_ctx()
    cond = {"type": "count_query", "where": {}, "operator": ">=", "value": 1}
    with pytest.raises(ValueError, match="count_query"):
        evaluate_condition(cond, ctx)


def test_estimate_sum_raises():
    ctx = _make_ctx()
    cond = {"type": "estimate_sum", "where": {}, "operator": ">=", "value": 1}
    with pytest.raises(ValueError, match="estimate_sum"):
        evaluate_condition(cond, ctx)
