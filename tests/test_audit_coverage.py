"""Regression tests for S4: audit trail must cover mutations on every
entity, not just issues. The README claims "audit trail on every
mutation" — this is the contract we hold to.

Covers: rule, label, project, team, membership.
"""
import pytest

from tests.conftest import make_team


async def _bootstrap(client):
    team = await make_team(client)
    api_key = team["api_key"]
    user_id = team["_setup_user_id"]
    return team, api_key, user_id, {"X-API-Key": api_key, "X-User-Id": user_id}


@pytest.mark.asyncio
async def test_rule_create_is_audited(client):
    team, _, user_id, headers = await _bootstrap(client)
    rule_resp = await client.post(
        f"/api/v1/teams/{team['id']}/rules",
        headers=headers,
        json={
            "name": "auditable rule",
            "trigger": "issue.created",
            "conditions": {"type": "field_equals", "field": "title", "value": "x"},
            "actions": [{"type": "add_label", "label": "x"}],
        },
    )
    assert rule_resp.status_code == 201
    rule_id = rule_resp.json()["data"]["id"]

    audit = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "rule", "entity_id": rule_id, "action": "create"},
    )
    assert audit.status_code == 200
    entries = audit.json()["data"]
    assert len(entries) == 1
    assert entries[0]["user_id"] == user_id


@pytest.mark.asyncio
async def test_rule_delete_is_audited(client):
    team, _, user_id, headers = await _bootstrap(client)
    rule_resp = await client.post(
        f"/api/v1/teams/{team['id']}/rules",
        headers=headers,
        json={
            "name": "doomed",
            "trigger": "issue.created",
            "conditions": {"type": "field_equals", "field": "title", "value": "x"},
            "actions": [{"type": "add_label", "label": "x"}],
        },
    )
    rid = rule_resp.json()["data"]["id"]
    await client.delete(f"/api/v1/rules/{rid}", headers=headers)

    audit = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "rule", "entity_id": rid, "action": "delete"},
    )
    entries = audit.json()["data"]
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_label_mutations_are_audited(client):
    team, _, user_id, headers = await _bootstrap(client)
    label_resp = await client.post(
        f"/api/v1/teams/{team['id']}/labels",
        headers=headers,
        json={"name": "bug"},
    )
    label_id = label_resp.json()["data"]["id"]
    await client.patch(
        f"/api/v1/labels/{label_id}",
        headers=headers,
        json={"color": "#ff0000"},
    )
    await client.delete(f"/api/v1/labels/{label_id}", headers=headers)

    audit = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "label"},
    )
    actions = {e["action"] for e in audit.json()["data"]}
    assert actions == {"create", "update", "delete"}, (
        f"Expected create+update+delete audit entries for label, got {actions}"
    )


@pytest.mark.asyncio
async def test_project_mutations_are_audited(client):
    team, _, user_id, headers = await _bootstrap(client)
    proj_resp = await client.post(
        f"/api/v1/teams/{team['id']}/projects",
        headers=headers,
        json={"name": "auditable"},
    )
    pid = proj_resp.json()["data"]["id"]
    await client.patch(f"/api/v1/projects/{pid}", headers=headers, json={"name": "renamed"})
    await client.delete(f"/api/v1/projects/{pid}", headers=headers)

    audit = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "project"},
    )
    actions = {e["action"] for e in audit.json()["data"]}
    assert actions == {"create", "update", "delete"}


@pytest.mark.asyncio
async def test_member_add_is_audited(client):
    team, _, user_id, headers = await _bootstrap(client)
    add = await client.post(
        f"/api/v1/teams/{team['id']}/users",
        headers=headers,
        json={"name": "Alice", "email": "alice@x.test"},
    )
    assert add.status_code == 201
    new_user_id = add.json()["data"]["id"]

    audit = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "membership", "action": "create"},
    )
    entries = audit.json()["data"]
    assert len(entries) == 1
    assert entries[0]["entity_id"] == new_user_id
    assert entries[0]["user_id"] == user_id  # the adder, not the added


@pytest.mark.asyncio
async def test_team_settings_update_is_audited(client):
    team, _, user_id, headers = await _bootstrap(client)
    patch = await client.patch(
        f"/api/v1/teams/{team['id']}",
        headers=headers,
        json={"settings": {"archive_days": 14, "triage_enabled": False}},
    )
    assert patch.status_code == 200
    audit = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "team", "action": "update"},
    )
    assert len(audit.json()["data"]) == 1
