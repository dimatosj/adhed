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


# NOTE: make_team now bootstraps via /setup, which creates an initial
# "Setup" user as OWNER. Users added via POST /teams/{id}/users after
# that default to MEMBER. Tests below account for that pre-existing user.


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
    # Alice is the second member (setup user was first) → defaults to MEMBER
    assert data["role"] == "member"


@pytest.mark.asyncio
async def test_create_second_user_is_member(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

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
    # Setup user + Alice + Bob
    assert len(body["data"]) == 3
    assert body["meta"]["total"] == 3


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

    # Setup user + Alice (dedup) = 2
    list_resp = await client.get(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
    )
    assert len(list_resp.json()["data"]) == 2
