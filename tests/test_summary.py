from datetime import date, timedelta

import pytest


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
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
        "states": states,
    }


@pytest.mark.asyncio
async def test_summary_basic(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Create issues in various states
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Triage issue"},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Started issue", "state_id": states["started"]["id"]},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Completed issue", "state_id": states["completed"]["id"]},
    )

    resp = await client.get(
        f"/api/v1/teams/{team_id}/summary",
        headers={"X-API-Key": setup["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["triage_count"] == 1
    assert data["by_state_type"]["triage"] == 1
    assert data["by_state_type"]["started"] == 1
    assert data["by_state_type"]["completed"] == 1

    # recently_completed should include the completed issue (created just now)
    assert len(data["recently_completed"]) == 1
    assert data["recently_completed"][0]["title"] == "Completed issue"


@pytest.mark.asyncio
async def test_summary_overdue(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    past_date = (date.today() - timedelta(days=3)).isoformat()

    # Create an overdue issue (past due_date, in started state)
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={
            "title": "Overdue task",
            "state_id": states["started"]["id"],
            "due_date": past_date,
        },
    )

    resp = await client.get(
        f"/api/v1/teams/{team_id}/summary",
        headers={"X-API-Key": setup["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert len(data["overdue"]) == 1
    assert data["overdue"][0]["title"] == "Overdue task"
    assert data["overdue"][0]["days_overdue"] == 3
