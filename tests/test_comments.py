import pytest


async def make_team(client, name="Acme", key="acme"):
    resp = await client.post("/api/v1/teams", json={"name": name, "key": key})
    assert resp.status_code == 201
    return resp.json()["data"]


async def make_user(client, team_id, api_key, name="Alice", email="alice@example.com"):
    resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": name, "email": email},
    )
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.fixture
async def setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    user = await make_user(client, team_id, api_key)
    user_id = user["id"]
    headers = {"X-API-Key": api_key, "X-User-Id": user_id}

    # Create an issue to comment on
    issue_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Commentable issue"},
    )
    assert issue_resp.status_code == 201
    issue_id = issue_resp.json()["data"]["id"]

    return {
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
        "issue_id": issue_id,
    }


@pytest.mark.asyncio
async def test_add_comment(client, setup):
    headers = setup["headers"]
    issue_id = setup["issue_id"]

    resp = await client.post(
        f"/api/v1/issues/{issue_id}/comments",
        headers=headers,
        json={"body": "This is a comment"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["body"] == "This is a comment"
    assert data["issue_id"] == issue_id
    assert data["user_id"] == setup["user_id"]


@pytest.mark.asyncio
async def test_list_comments(client, setup):
    headers = setup["headers"]
    issue_id = setup["issue_id"]
    api_key = setup["api_key"]

    # Add two comments
    await client.post(
        f"/api/v1/issues/{issue_id}/comments",
        headers=headers,
        json={"body": "First comment"},
    )
    await client.post(
        f"/api/v1/issues/{issue_id}/comments",
        headers=headers,
        json={"body": "Second comment"},
    )

    # List comments
    resp = await client.get(
        f"/api/v1/issues/{issue_id}/comments",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 2
    assert body["data"][0]["body"] == "First comment"
    assert body["data"][1]["body"] == "Second comment"
