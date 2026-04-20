import pytest


async def make_team(client, name="Acme", key="acme"):
    resp = await client.post("/api/v1/teams", json={"name": name, "key": key})
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_create_user(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": "Alice", "email": "alice@example.com"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
    assert data["role"] == "owner"


@pytest.mark.asyncio
async def test_create_second_user_is_member(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": "Alice", "email": "alice@example.com"},
    )

    resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": "Bob", "email": "bob@example.com"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["role"] == "member"


@pytest.mark.asyncio
async def test_list_users(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": "Alice", "email": "alice@example.com"},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": "Bob", "email": "bob@example.com"},
    )

    resp = await client.get(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_duplicate_email_same_team(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": "Alice", "email": "alice@example.com"},
    )

    # Adding same email again should succeed (user already in team)
    resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": "Alice", "email": "alice@example.com"},
    )
    assert resp.status_code == 201

    # Team should still have only 1 member
    list_resp = await client.get(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
    )
    assert len(list_resp.json()["data"]) == 1
