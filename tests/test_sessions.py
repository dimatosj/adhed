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


@pytest.mark.asyncio
async def test_create_braindump_session(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump", "payload": {"items": []}},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    session = resp.json()["data"]
    assert session["type"] == "braindump"
    assert session["state"] == "active"
    assert session["payload"] == {"items": []}
    assert session["completed_at"] is None


@pytest.mark.asyncio
async def test_create_readiness_prep_session(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "readiness_prep"},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["type"] == "readiness_prep"


@pytest.mark.asyncio
async def test_create_scheduling_session(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "scheduling"},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["type"] == "scheduling"


@pytest.mark.asyncio
async def test_invalid_session_type_returns_422(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "invalid_type"},
        headers=setup["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_sessions(client, setup):
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump"},
        headers=setup["headers"],
    )
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "readiness_prep"},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 2
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_list_sessions_filter_by_type(client, setup):
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump"},
        headers=setup["headers"],
    )
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "readiness_prep"},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/sessions?type=braindump",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 1
    assert resp.json()["data"][0]["type"] == "braindump"


@pytest.mark.asyncio
async def test_list_sessions_filter_by_state(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump"},
        headers=setup["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    await client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"state": "completed"},
        headers=setup["headers"],
    )

    await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump"},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/sessions?state=active",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_get_session(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump", "payload": {"items": ["wash car"]}},
        headers=setup["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    resp = await client.get(
        f"/api/v1/sessions/{session_id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == session_id
    assert resp.json()["data"]["payload"] == {"items": ["wash car"]}


@pytest.mark.asyncio
async def test_get_nonexistent_session_returns_404(client, setup):
    resp = await client.get(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000",
        headers=setup["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_session_payload(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump", "payload": {"items": []}},
        headers=setup["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"payload": {"items": ["task1", "task2"], "classified": True}},
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["payload"]["items"] == ["task1", "task2"]
    assert resp.json()["data"]["state"] == "active"


@pytest.mark.asyncio
async def test_complete_session_sets_completed_at(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump"},
        headers=setup["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"state": "completed"},
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    session = resp.json()["data"]
    assert session["state"] == "completed"
    assert session["completed_at"] is not None


@pytest.mark.asyncio
async def test_abandon_session_sets_completed_at(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump"},
        headers=setup["headers"],
    )
    session_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"state": "abandoned"},
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == "abandoned"
    assert resp.json()["data"]["completed_at"] is not None


@pytest.mark.asyncio
async def test_session_audited(client, setup):
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump"},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/audit?entity_type=session",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 1
    assert entries[0]["entity_type"] == "session"
    assert entries[0]["action"] == "create"
