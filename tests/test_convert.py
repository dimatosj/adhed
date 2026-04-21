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


@pytest.fixture
async def setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    user = await make_user(client, team_id, api_key)
    user_id = user["id"]
    headers = {"X-API-Key": api_key, "X-User-Id": user_id}
    return {
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_convert_issue_to_project(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    api_key = setup["api_key"]

    # Create an issue
    issue_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Big feature", "description": "This needs a project"},
    )
    assert issue_resp.status_code == 201
    issue_id = issue_resp.json()["data"]["id"]

    # Convert to project
    convert_resp = await client.post(
        f"/api/v1/issues/{issue_id}/convert-to-project",
        headers={"X-API-Key": api_key},
    )
    assert convert_resp.status_code == 201
    data = convert_resp.json()["data"]

    # Verify project was created
    project = data["project"]
    assert project["name"] == "Big feature"
    assert project["description"] == "This needs a project"
    assert project["team_id"] == team_id

    # Verify issue now belongs to the project
    issue = data["issue"]
    assert issue["project_id"] == project["id"]

    # Verify via GET on the project
    proj_resp = await client.get(
        f"/api/v1/projects/{project['id']}",
        headers={"X-API-Key": api_key},
    )
    assert proj_resp.status_code == 200
    proj_data = proj_resp.json()["data"]
    assert proj_data["name"] == "Big feature"
    # The issue should count in the project's issue_counts
    assert proj_data["issue_counts"]["triage"] == 1
