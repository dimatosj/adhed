import pytest

from taskstore.models.enums import StateType


async def make_team(client, name="Transitions", key="trans"):
    resp = await client.post("/api/v1/teams", json={"name": name, "key": key})
    assert resp.status_code == 201
    return resp.json()["data"]


async def make_user(client, team_id, api_key, name="Bob", email="bob@example.com"):
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
        "team": team,
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
        "states": states,
    }


@pytest.mark.asyncio
async def test_valid_transition_triage_to_backlog(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Create issue in triage (default)
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Triage issue"},
    )
    assert resp.status_code == 201
    issue_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["state"]["type"] == "triage"

    # Move to backlog
    backlog_id = states["backlog"]["id"]
    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"state_id": backlog_id},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["state"]["type"] == "backlog"


@pytest.mark.asyncio
async def test_invalid_transition_triage_to_completed(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Create issue in triage (default)
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Triage issue"},
    )
    assert resp.status_code == 201
    issue_id = resp.json()["data"]["id"]

    # Attempt invalid transition: triage -> completed
    completed_id = states["completed"]["id"]
    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"state_id": completed_id},
    )
    assert patch_resp.status_code == 422


@pytest.mark.asyncio
async def test_valid_transition_started_to_completed(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Create issue directly in started state
    started_id = states["started"]["id"]
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Started issue", "state_id": started_id},
    )
    assert resp.status_code == 201
    issue_id = resp.json()["data"]["id"]

    # Move to completed
    completed_id = states["completed"]["id"]
    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"state_id": completed_id},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["state"]["type"] == "completed"


@pytest.mark.asyncio
async def test_reopen_completed_to_unstarted(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Create in started
    started_id = states["started"]["id"]
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Will reopen", "state_id": started_id},
    )
    assert resp.status_code == 201
    issue_id = resp.json()["data"]["id"]

    # Move to completed
    completed_id = states["completed"]["id"]
    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"state_id": completed_id},
    )
    assert patch_resp.status_code == 200

    # Reopen: completed -> unstarted
    unstarted_id = states["unstarted"]["id"]
    reopen_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"state_id": unstarted_id},
    )
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["data"]["state"]["type"] == "unstarted"


@pytest.mark.asyncio
async def test_same_category_transition_allowed(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    api_key = setup["api_key"]
    states = setup["states"]

    # Create a custom "In Review" state under started category
    create_state_resp = await client.post(
        f"/api/v1/teams/{team_id}/states",
        headers=headers,
        json={"name": "In Review", "type": "started", "color": "#ff9900", "position": 99},
    )
    assert create_state_resp.status_code == 201
    in_review_state = create_state_resp.json()["data"]
    assert in_review_state["type"] == "started"

    # Create issue in the default "In Progress" / started state
    started_id = states["started"]["id"]
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "In progress issue", "state_id": started_id},
    )
    assert resp.status_code == 201
    issue_id = resp.json()["data"]["id"]

    # Move to "In Review" (also started category) — same category transition
    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"state_id": in_review_state["id"]},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["state"]["name"] == "In Review"
