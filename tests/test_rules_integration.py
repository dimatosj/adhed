"""Integration tests for the rules engine with the API."""

import uuid

import pytest

from taskstore.models.enums import StateType

from tests.conftest import make_team, make_user, get_states_by_type


async def make_label(client, team_id, api_key, user_id, name, color=None):
    resp = await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key, "X-User-Id": user_id},
        json={"name": name, "color": color},
    )
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.fixture
async def rules_setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    # Use the OWNER user created by /setup — rules, state changes, etc.
    # all require ADMIN+ now.
    user_id = team["_setup_user_id"]
    headers = {"X-API-Key": api_key, "X-User-Id": user_id}
    states = await get_states_by_type(client, team_id, api_key)
    health_label = await make_label(client, team_id, api_key, user_id, "health")
    return {
        "team": team,
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
        "states": states,
        "health_label": health_label,
    }


@pytest.mark.asyncio
async def test_auto_label_rule(client, rules_setup):
    s = rules_setup
    headers = s["headers"]
    team_id = s["team_id"]

    # Create rule: when issue.created, if title contains "dentist" or "gym", add label "health"
    rule_resp = await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers=s["headers"],
        json={
            "name": "Auto-label health issues",
            "trigger": "issue.created",
            "conditions": {
                "type": "or",
                "conditions": [
                    {"type": "field_contains", "field": "title", "value": "dentist"},
                    {"type": "field_contains", "field": "title", "value": "gym"},
                ],
            },
            "actions": [{"type": "add_label", "label": "health"}],
        },
    )
    assert rule_resp.status_code == 201

    # Create issue with "dentist" in title
    issue_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Call the dentist"},
    )
    assert issue_resp.status_code == 201
    data = issue_resp.json()["data"]
    label_names = [l["name"] for l in data["labels"]]
    assert "health" in label_names

    # Create issue WITHOUT matching title — should NOT get the label
    issue_resp2 = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Buy groceries"},
    )
    assert issue_resp2.status_code == 201
    data2 = issue_resp2.json()["data"]
    label_names2 = [l["name"] for l in data2["labels"]]
    assert "health" not in label_names2


@pytest.mark.asyncio
async def test_reject_rule_blocks_operation(client, rules_setup):
    s = rules_setup
    headers = s["headers"]
    team_id = s["team_id"]
    states = s["states"]

    # Create rule: when issue.state_changed from triage, if priority == 0 (none), reject
    rule_resp = await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers=s["headers"],
        json={
            "name": "Require priority before accepting",
            "trigger": "issue.state_changed",
            "conditions": {
                "type": "and",
                "conditions": [
                    {"type": "field_equals", "field": "from_state_type", "value": "triage"},
                    {"type": "field_lte", "field": "priority", "value": 0},
                ],
            },
            "actions": [
                {
                    "type": "reject",
                    "message": "Set priority before accepting from triage.",
                }
            ],
        },
    )
    assert rule_resp.status_code == 201

    # Create issue (defaults to triage, priority=0)
    issue_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Unprioritised task"},
    )
    assert issue_resp.status_code == 201
    issue_id = issue_resp.json()["data"]["id"]
    assert issue_resp.json()["data"]["state"]["type"] == StateType.TRIAGE.value
    assert issue_resp.json()["data"]["priority"] == 0

    # Try to move to backlog — should be rejected
    backlog_state_id = states["backlog"]["id"]
    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"state_id": backlog_state_id},
    )
    assert patch_resp.status_code == 422
    detail = patch_resp.json()["detail"]
    assert detail["errors"][0]["message"] == "Set priority before accepting from triage."
    assert detail["errors"][0]["rule_name"] == "Require priority before accepting"


@pytest.mark.asyncio
async def test_rule_crud(client, rules_setup):
    """Test basic CRUD operations for rules."""
    s = rules_setup
    team_id = s["team_id"]
    api_key = s["api_key"]
    api_headers = {"X-API-Key": api_key, "X-User-Id": s["user_id"]}

    # Create
    create_resp = await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers=api_headers,
        json={
            "name": "Test rule",
            "trigger": "issue.created",
            "conditions": {"type": "field_equals", "field": "priority", "value": 1},
            "actions": {"type": "add_label", "label": "low"},
            "priority": 50,
        },
    )
    assert create_resp.status_code == 201
    rule = create_resp.json()["data"]
    rule_id = rule["id"]
    assert rule["name"] == "Test rule"
    assert rule["priority"] == 50
    assert rule["enabled"] is True
    # Actions should be normalised to list
    assert isinstance(rule["actions"], list)

    # List
    list_resp = await client.get(
        f"/api/v1/teams/{team_id}/rules",
        headers=api_headers,
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["meta"]["total"] == 1

    # Update
    patch_resp = await client.patch(
        f"/api/v1/rules/{rule_id}",
        headers=api_headers,
        json={"name": "Updated rule", "enabled": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["name"] == "Updated rule"
    assert patch_resp.json()["data"]["enabled"] is False

    # Delete
    del_resp = await client.delete(
        f"/api/v1/rules/{rule_id}",
        headers=api_headers,
    )
    assert del_resp.status_code == 204

    # Verify deleted
    list_resp2 = await client.get(
        f"/api/v1/teams/{team_id}/rules",
        headers=api_headers,
    )
    assert list_resp2.status_code == 200
    assert list_resp2.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_broken_rule_fails_loudly(client, rules_setup):
    """A rule with an unknown condition type must NOT silently skip —
    the triggering write must fail with an error identifying the broken rule.

    Regression test for C3: rules/evaluator.py used to `except ValueError: continue`,
    which caused WIP-limit and similar enforcement rules to silently stop working
    on any JSON shape typo. Security-relevant because rules are meant to be
    deterministic enforcement, not best-effort.
    """
    s = rules_setup
    headers = s["headers"]
    api_headers = {"X-API-Key": s["api_key"], "X-User-Id": s["user_id"]}
    team_id = s["team_id"]

    # Create a rule with an unknown condition type. The service accepts it
    # (JSONB is opaque) but the evaluator will raise ValueError when it fires.
    rule_resp = await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers=api_headers,
        json={
            "name": "Broken rule",
            "trigger": "issue.created",
            "conditions": {"type": "not_a_real_condition_type"},
            "actions": [{"type": "add_label", "label": "health"}],
        },
    )
    assert rule_resp.status_code == 201

    # Trigger the rule by creating an issue. Expected: 422 with rule info.
    create_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "should not succeed"},
    )
    assert create_resp.status_code == 422, (
        f"Expected loud 422, got {create_resp.status_code}: {create_resp.text}"
    )
    body = create_resp.json()
    # Error envelope should name the broken rule so ops can find it
    errors = body.get("detail", {}).get("errors") or body.get("errors") or []
    assert any(
        "not_a_real_condition_type" in (e.get("message") or "")
        or "broken" in (e.get("message") or "").lower()
        or (e.get("rule_name") == "Broken rule")
        for e in errors
    ), f"Error payload should identify the broken rule: {body}"


@pytest.mark.asyncio
async def test_set_field_rejects_non_whitelisted_field_at_create(client, rules_setup):
    """Regression test for S1: set_field used to blindly setattr() any
    field name, letting a rule teleport issues across tenants
    (field="team_id") or forge created_by. Rule creation must reject
    dangerous field names at write time.
    """
    s = rules_setup
    api_headers = {"X-API-Key": s["api_key"], "X-User-Id": s["user_id"]}
    team_id = s["team_id"]

    dangerous_fields = ["team_id", "created_by", "id", "archived_at", "title_search"]
    for field in dangerous_fields:
        resp = await client.post(
            f"/api/v1/teams/{team_id}/rules",
            headers=api_headers,
            json={
                "name": f"Evil rule targeting {field}",
                "trigger": "issue.created",
                "conditions": {"type": "field_equals", "field": "title", "value": "x"},
                "actions": [{"type": "set_field", "field": field, "value": "pwn"}],
            },
        )
        assert resp.status_code == 400, (
            f"Rule with set_field={field!r} should be rejected at create, "
            f"got {resp.status_code}: {resp.text}"
        )


@pytest.mark.asyncio
async def test_count_query_excludes_archived_issues(client, rules_setup):
    """Regression test for M6: WIP limit rules used to count archived issues.

    A team with a "max 2 started issues" rule could be soft-deadlocked by
    completing and archiving old work: the archived rows still counted toward
    the limit, so new work couldn't start. Count queries should exclude
    archived issues by default.
    """
    from datetime import datetime
    from sqlalchemy import update as sa_update
    from taskstore.models.issue import Issue
    from tests.conftest import TestSessionLocal

    s = rules_setup
    headers = s["headers"]
    api_headers = {"X-API-Key": s["api_key"], "X-User-Id": s["user_id"]}
    team_id = s["team_id"]
    started_state_id = s["states"]["started"]["id"]
    unstarted_state_id = s["states"]["unstarted"]["id"]

    # Rule: WIP limit of 2 started issues. Issue is flushed before rules
    # run, so "reject when count >= 3" is how you express "max 2 allowed."
    rule_resp = await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers=api_headers,
        json={
            "name": "WIP limit: started <= 2",
            "trigger": "issue.created",
            "conditions": {
                "type": "count_query",
                "where": {"state_type": "started"},
                "operator": ">=",
                "value": 3,
            },
            "actions": [{"type": "reject", "message": "WIP limit reached"}],
        },
    )
    assert rule_resp.status_code == 201

    # Create two started issues — fill the WIP quota
    for i in range(2):
        resp = await client.post(
            f"/api/v1/teams/{team_id}/issues",
            headers=headers,
            json={"title": f"started {i}", "state_id": started_state_id},
        )
        assert resp.status_code == 201, resp.text

    # Third create must be rejected — limit is full
    blocked = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "blocked", "state_id": started_state_id},
    )
    assert blocked.status_code == 422

    # Archive one of the started issues by setting archived_at directly.
    # (No archive endpoint yet — direct DB write simulates an archiver job.)
    from taskstore.utils.time import now_utc
    async with TestSessionLocal() as session:
        await session.execute(
            sa_update(Issue)
            .where(Issue.team_id == uuid.UUID(team_id), Issue.state_id == uuid.UUID(started_state_id))
            .values(archived_at=now_utc())
            .execution_options(synchronize_session=False)
        )
        await session.commit()

    # With the previous started issues archived, active WIP count is 0.
    # A new started issue should now be allowed.
    after_archive = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "should now succeed", "state_id": started_state_id},
    )
    assert after_archive.status_code == 201, (
        f"Archived issues should not count toward WIP limit: {after_archive.text}"
    )


@pytest.mark.asyncio
async def test_set_field_allows_whitelisted_fields_at_create(client, rules_setup):
    """Whitelisted fields must still be accepted at rule create."""
    s = rules_setup
    api_headers = {"X-API-Key": s["api_key"], "X-User-Id": s["user_id"]}
    team_id = s["team_id"]

    for field in ("priority", "estimate", "assignee_id", "project_id",
                  "due_date", "state_id"):
        resp = await client.post(
            f"/api/v1/teams/{team_id}/rules",
            headers=api_headers,
            json={
                "name": f"Legit rule setting {field}",
                "trigger": "issue.created",
                "conditions": {"type": "field_equals", "field": "title", "value": "x"},
                "actions": [{"type": "set_field", "field": field, "value": None}],
            },
        )
        assert resp.status_code == 201, (
            f"Whitelisted field {field!r} should be accepted, "
            f"got {resp.status_code}: {resp.text}"
        )
