"""Integration tests for the rules engine with the API."""

import pytest

from taskstore.models.enums import StateType


async def make_team(client, name="RulesTeam", key="rules"):
    resp = await client.post("/api/v1/teams", json={"name": name, "key": key})
    assert resp.status_code == 201
    return resp.json()["data"]


async def make_user(client, team_id, api_key, name="Alice", email="alice@rules.test"):
    resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": name, "email": email},
    )
    assert resp.status_code == 201
    return resp.json()["data"]


async def get_states_by_type(client, team_id, api_key):
    resp = await client.get(
        f"/api/v1/teams/{team_id}/states",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    states = resp.json()["data"]
    by_type = {}
    for s in states:
        by_type[s["type"]] = s
    return by_type


async def make_label(client, team_id, api_key, name, color=None):
    resp = await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
        json={"name": name, "color": color},
    )
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.fixture
async def rules_setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    user = await make_user(client, team_id, api_key)
    user_id = user["id"]
    headers = {"X-API-Key": api_key, "X-User-Id": user_id}
    states = await get_states_by_type(client, team_id, api_key)
    health_label = await make_label(client, team_id, api_key, "health")
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
        headers={"X-API-Key": s["api_key"]},
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
        headers={"X-API-Key": s["api_key"]},
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
    api_headers = {"X-API-Key": api_key}

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
    assert list_resp2.json()["meta"]["total"] == 0
