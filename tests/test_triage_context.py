import pytest


@pytest.fixture
async def setup(client):
    resp = await client.post("/api/v1/setup", json={
        "team_name": "Home", "team_key": "HOME",
        "user_name": "John", "user_email": "john@example.com",
        "include_default_labels": False,
    })
    data = resp.json()
    headers = {"X-API-Key": data["api_key"], "X-User-Id": str(data["user_id"])}
    return {"team_id": data["team_id"], "user_id": data["user_id"], "headers": headers}


SAMPLE_TRIAGE = {
    "breakdown_hints": ["split into sub-tasks", "needs research first"],
    "blockers": ["waiting on plumber quote"],
    "emotional_weight": "high",
    "raw_context": "John mentioned this is stressing him out during braindump",
}


@pytest.mark.asyncio
async def test_create_issue_with_triage_context(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Fix kitchen faucet", "priority": 2, "triage_context": SAMPLE_TRIAGE},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    issue = resp.json()["data"]
    assert issue["triage_context"] == SAMPLE_TRIAGE


@pytest.mark.asyncio
async def test_create_issue_without_triage_context(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Regular task"},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["triage_context"] is None


@pytest.mark.asyncio
async def test_update_issue_triage_context(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Task to triage"},
        headers=setup["headers"],
    )
    issue_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        json={"triage_context": SAMPLE_TRIAGE},
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["triage_context"] == SAMPLE_TRIAGE


@pytest.mark.asyncio
async def test_clear_triage_context(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Task", "triage_context": SAMPLE_TRIAGE},
        headers=setup["headers"],
    )
    issue_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        json={"triage_context": None},
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["triage_context"] is None


@pytest.mark.asyncio
async def test_triage_context_in_get(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Triaged task", "triage_context": SAMPLE_TRIAGE},
        headers=setup["headers"],
    )
    issue_id = create_resp.json()["data"]["id"]

    resp = await client.get(
        f"/api/v1/issues/{issue_id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["triage_context"] == SAMPLE_TRIAGE


@pytest.mark.asyncio
async def test_triage_context_in_list(client, setup):
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "With triage", "triage_context": SAMPLE_TRIAGE},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/issues",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    issues = resp.json()["data"]
    assert len(issues) == 1
    assert issues[0]["triage_context"] == SAMPLE_TRIAGE
