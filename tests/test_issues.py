import pytest

from taskstore.models.enums import StateType


async def make_team(client, name="Acme", key="acme"):
    # Bootstrap via /setup (first team; POST /teams now requires OWNER auth).
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": name,
            "team_key": key,
            "user_name": "Setup",
            "user_email": f"setup-{key}@example.com",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return {
        "id": data["team_id"],
        "name": data["team_name"],
        "key": data["team_key"],
        "api_key": data["api_key"],
        "_setup_user_id": data["user_id"],
    }


async def make_user(client, team_id, api_key, name="Alice", email="alice@example.com"):
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
async def test_create_issue(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Fix login bug", "priority": 2},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["title"] == "Fix login bug"
    assert data["priority"] == 2
    assert data["type"] == "task"
    assert data["created_by"] == setup["user_id"]


@pytest.mark.asyncio
async def test_create_issue_defaults_to_triage(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Team has triage_enabled=True by default
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Triage me"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["state"]["type"] == StateType.TRIAGE.value
    assert data["state"]["id"] == states["triage"]["id"]


@pytest.mark.asyncio
async def test_get_issue(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    api_key = setup["api_key"]

    create_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Get me", "description": "A description", "priority": 3},
    )
    assert create_resp.status_code == 201
    issue_id = create_resp.json()["data"]["id"]

    get_resp = await client.get(
        f"/api/v1/issues/{issue_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["id"] == issue_id
    assert data["title"] == "Get me"
    assert data["description"] == "A description"
    assert data["priority"] == 3
    assert data["type"] == "task"
    assert data["team_id"] == team_id
    assert data["created_by"] == setup["user_id"]
    assert data["state"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
    assert data["archived_at"] is None
    assert data["labels"] == []


@pytest.mark.asyncio
async def test_update_issue(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    create_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Old title", "priority": 1},
    )
    assert create_resp.status_code == 201
    issue_id = create_resp.json()["data"]["id"]

    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"title": "New title", "priority": 5},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()["data"]
    assert data["title"] == "New title"
    assert data["priority"] == 5


@pytest.mark.asyncio
async def test_list_issues_filter_by_state_type(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Create an issue in triage (default)
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Triage issue"},
    )

    # Create an issue in started state
    started_state_id = states["started"]["id"]
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Started issue", "state_id": started_state_id},
    )

    # Create an issue in completed state
    completed_state_id = states["completed"]["id"]
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Done issue", "state_id": completed_state_id},
    )

    # Filter by started only
    resp = await client.get(
        f"/api/v1/teams/{team_id}/issues",
        headers={"X-API-Key": setup["api_key"]},
        params={"state_type": "started"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["title"] == "Started issue"

    # Filter by started,completed
    resp = await client.get(
        f"/api/v1/teams/{team_id}/issues",
        headers={"X-API-Key": setup["api_key"]},
        params={"state_type": "started,completed"},
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_list_issues_full_text_search(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Call the dentist"},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Buy groceries"},
    )

    resp = await client.get(
        f"/api/v1/teams/{team_id}/issues",
        headers={"X-API-Key": setup["api_key"]},
        params={"title_search": "dentist"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["title"] == "Call the dentist"


@pytest.mark.asyncio
async def test_create_subtask(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    # Create parent
    parent_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent task"},
    )
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["data"]["id"]

    # Create child
    child_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Child task", "parent_id": parent_id},
    )
    assert child_resp.status_code == 201
    child_data = child_resp.json()["data"]
    assert child_data["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_delete_issue_with_active_children_fails(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    # Create parent
    parent_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent"},
    )
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["data"]["id"]

    # Create child (defaults to triage state — active)
    child_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Child", "parent_id": parent_id},
    )
    assert child_resp.status_code == 201

    # Attempt to delete parent should fail with 409
    del_resp = await client.delete(
        f"/api/v1/issues/{parent_id}",
        headers=headers,
    )
    assert del_resp.status_code == 409
