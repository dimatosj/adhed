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
async def test_link_fragment_to_session(client, setup):
    frag_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/fragments",
        json={"text": "Braindump note", "type": "memory"},
        headers=setup["headers"],
    )
    assert frag_resp.status_code == 201
    frag_id = frag_resp.json()["data"]["id"]

    session_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "braindump", "payload": {"items": []}},
        headers=setup["headers"],
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["data"]["id"]

    link_resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "session", "target_id": session_id},
        headers=setup["headers"],
    )
    assert link_resp.status_code == 201
    link = link_resp.json()["data"]
    assert link["target_type"] == "session"
    assert link["target_id"] == session_id
    assert link["summary"] == "braindump session"
    assert link["detail"]["type"] == "braindump"
    assert link["detail"]["state"] == "active"


@pytest.mark.asyncio
async def test_link_to_nonexistent_session_returns_404(client, setup):
    frag_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/fragments",
        json={"text": "Orphan", "type": "memory"},
        headers=setup["headers"],
    )
    frag_id = frag_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "session", "target_id": "00000000-0000-0000-0000-000000000000"},
        headers=setup["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_links_includes_session(client, setup):
    frag_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/fragments",
        json={"text": "Note", "type": "memory"},
        headers=setup["headers"],
    )
    frag_id = frag_resp.json()["data"]["id"]

    session_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/sessions",
        json={"type": "readiness_prep"},
        headers=setup["headers"],
    )
    session_id = session_resp.json()["data"]["id"]

    await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "session", "target_id": session_id},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/fragments/{frag_id}/links?target_type=session",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    links = resp.json()["data"]
    assert len(links) == 1
    assert links[0]["target_type"] == "session"
