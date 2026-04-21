import pytest

from tests.conftest import make_team, make_user, get_states_by_type


@pytest.fixture
async def setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    user = await make_user(client, team_id, api_key)
    user_id = user["id"]
    headers = {"X-API-Key": api_key, "X-User-Id": user_id}
    states = await get_states_by_type(client, team_id, api_key)
    return {
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
        "states": states,
    }


@pytest.mark.asyncio
async def test_batch_create(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues/batch",
        headers=headers,
        json=[
            {"title": "Batch 1"},
            {"title": "Batch 2"},
            {"title": "Batch 3"},
        ],
    )
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert len(results) == 3
    for r in results:
        assert r["error"] is None
        assert r["data"]["title"].startswith("Batch")


@pytest.mark.asyncio
async def test_batch_create_partial_rejection(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    api_key = setup["api_key"]

    # Create a rule that rejects issues with "REJECT" in the title
    rule_resp = await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers={"X-API-Key": api_key},
        json={
            "name": "Reject REJECT titles",
            "trigger": "issue.created",
            "conditions": {
                "type": "field_contains",
                "field": "title",
                "value": "REJECT",
            },
            "actions": [
                {"type": "reject", "message": "Title contains REJECT"},
            ],
        },
    )
    assert rule_resp.status_code == 201

    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues/batch",
        headers=headers,
        json=[
            {"title": "Good issue 1"},
            {"title": "REJECT this one"},
            {"title": "Good issue 2"},
        ],
    )
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert len(results) == 3

    # First should succeed
    assert results[0]["error"] is None
    assert results[0]["data"]["title"] == "Good issue 1"

    # Second should be rejected
    assert results[1]["data"] is None
    assert "REJECT" in results[1]["error"]

    # Third should succeed
    assert results[2]["error"] is None
    assert results[2]["data"]["title"] == "Good issue 2"


@pytest.mark.asyncio
async def test_batch_update(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    started_state_id = states["started"]["id"]
    backlog_state_id = states["backlog"]["id"]

    # Create 3 issues in started state
    for i in range(3):
        resp = await client.post(
            f"/api/v1/teams/{team_id}/issues",
            headers=headers,
            json={"title": f"Started {i}", "state_id": started_state_id},
        )
        assert resp.status_code == 201

    # Batch update: move all started issues to backlog
    resp = await client.patch(
        f"/api/v1/teams/{team_id}/issues/batch",
        headers=headers,
        json={
            "filter": {"state_type": "started"},
            "update": {"state_id": str(backlog_state_id)},
        },
    )
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert len(results) == 3
    for r in results:
        assert r["state"]["type"] == "backlog"
