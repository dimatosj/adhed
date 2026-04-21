"""Pure unit tests for rule action preparation — no DB needed."""

from taskstore.rules.actions import prepare_action
from taskstore.rules.context import RuleContext


def _make_ctx(**overrides):
    defaults = {
        "issue": {
            "title": "Fix login bug",
            "priority": 2,
            "assignee_id": "user-1",
            "project_id": "proj-1",
            "state": "In Progress",
        },
        "current_user": "user-1",
        "to_state": "In Progress",
    }
    defaults.update(overrides)
    return RuleContext(**defaults)


def test_reject_action():
    ctx = _make_ctx()
    action = {"type": "reject", "message": "Not allowed"}
    effect = prepare_action(action, ctx)
    assert effect.type == "reject"
    assert effect.params["message"] == "Not allowed"


def test_set_field_action():
    ctx = _make_ctx()
    action = {"type": "set_field", "field": "priority", "value": 5}
    effect = prepare_action(action, ctx)
    assert effect.type == "set_field"
    assert effect.params["field"] == "priority"
    assert effect.params["value"] == 5


def test_add_label_action():
    ctx = _make_ctx()
    action = {"type": "add_label", "label": "urgent"}
    effect = prepare_action(action, ctx)
    assert effect.type == "add_label"
    assert effect.params["label_name"] == "urgent"


def test_notify_action_with_template():
    ctx = _make_ctx()
    action = {
        "type": "notify",
        "message": "Issue '{title}' (priority {priority}) moved to {state}",
        "user_id": "$current_user",
    }
    effect = prepare_action(action, ctx)
    assert effect.type == "notify"
    assert effect.params["message"] == "Issue 'Fix login bug' (priority 2) moved to In Progress"
    assert effect.params["user_id"] == "user-1"


def test_add_comment_action():
    ctx = _make_ctx()
    action = {"type": "add_comment", "body": "Auto-comment for {title}"}
    effect = prepare_action(action, ctx)
    assert effect.type == "add_comment"
    assert effect.params["body"] == "Auto-comment for Fix login bug"
