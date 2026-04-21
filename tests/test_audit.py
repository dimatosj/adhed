import pytest

from tests.conftest import make_team


@pytest.fixture
async def setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    user_id = team["_setup_user_id"]
    headers = {"X-API-Key": api_key, "X-User-Id": user_id}
    return {
        "team": team,
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_issue_create_audited(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    # Create an issue
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Audited issue", "priority": 0},
    )
    assert resp.status_code == 201
    issue_id = resp.json()["data"]["id"]

    # Fetch audit log
    audit_resp = await client.get(
        f"/api/v1/teams/{team_id}/audit",
        headers=setup["headers"],
    )
    assert audit_resp.status_code == 200
    entries = audit_resp.json()["data"]

    # Should have at least one create entry for this issue
    create_entries = [
        e for e in entries
        if e["entity_id"] == issue_id and e["action"] == "create"
    ]
    assert len(create_entries) == 1
    entry = create_entries[0]
    assert entry["entity_type"] == "issue"
    assert entry["user_id"] == setup["user_id"]
    assert entry["team_id"] == team_id


@pytest.mark.asyncio
async def test_issue_update_audited_with_diff(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    # Create issue with title "Original" and priority 0
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Original", "priority": 0},
    )
    assert resp.status_code == 201
    issue_id = resp.json()["data"]["id"]

    # Update title to "Updated" and priority to 1
    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"title": "Updated", "priority": 1},
    )
    assert patch_resp.status_code == 200

    # Fetch update audit entries
    audit_resp = await client.get(
        f"/api/v1/teams/{team_id}/audit",
        headers=setup["headers"],
        params={"action": "update"},
    )
    assert audit_resp.status_code == 200
    entries = audit_resp.json()["data"]

    update_entries = [
        e for e in entries
        if e["entity_id"] == issue_id and e["action"] == "update"
    ]
    assert len(update_entries) == 1
    changes = update_entries[0]["changes"]

    assert "title" in changes
    assert changes["title"]["old"] == "Original"
    assert changes["title"]["new"] == "Updated"

    assert "priority" in changes
    assert changes["priority"]["old"] == 0
    assert changes["priority"]["new"] == 1
