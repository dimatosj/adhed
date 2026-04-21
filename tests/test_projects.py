import pytest

from tests.conftest import make_team, make_user, get_states_by_type


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
async def test_create_project(client, setup):
    team_id = setup["team_id"]
    api_key = setup["api_key"]

    resp = await client.post(
        f"/api/v1/teams/{team_id}/projects",
        headers={"X-API-Key": api_key},
        json={"name": "Project Alpha", "description": "First project"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Project Alpha"
    assert data["description"] == "First project"
    assert data["state"] == "planned"
    assert data["team_id"] == team_id


@pytest.mark.asyncio
async def test_list_projects(client, setup):
    team_id = setup["team_id"]
    api_key = setup["api_key"]

    await client.post(
        f"/api/v1/teams/{team_id}/projects",
        headers={"X-API-Key": api_key},
        json={"name": "Project A"},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/projects",
        headers={"X-API-Key": api_key},
        json={"name": "Project B"},
    )

    resp = await client.get(
        f"/api/v1/teams/{team_id}/projects",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_get_project_with_issue_counts(client, setup):
    team_id = setup["team_id"]
    api_key = setup["api_key"]
    headers = setup["headers"]
    states = setup["states"]

    # Create project
    proj_resp = await client.post(
        f"/api/v1/teams/{team_id}/projects",
        headers={"X-API-Key": api_key},
        json={"name": "Counted Project"},
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # Create 2 issues in the project (default triage state)
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Issue 1", "project_id": project_id},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={
            "title": "Issue 2",
            "project_id": project_id,
            "state_id": states["started"]["id"],
        },
    )

    # Get project with counts
    get_resp = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["issue_counts"]["triage"] == 1
    assert data["issue_counts"]["started"] == 1
    assert data["issue_counts"]["backlog"] == 0
    assert data["issue_counts"]["completed"] == 0


@pytest.mark.asyncio
async def test_delete_project_with_issues_fails(client, setup):
    team_id = setup["team_id"]
    api_key = setup["api_key"]
    headers = setup["headers"]

    # Create project
    proj_resp = await client.post(
        f"/api/v1/teams/{team_id}/projects",
        headers={"X-API-Key": api_key},
        json={"name": "Has Issues"},
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # Create issue in project
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Blocking issue", "project_id": project_id},
    )

    # Delete should fail with 409
    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"X-API-Key": api_key},
    )
    assert del_resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_empty_project(client, setup):
    team_id = setup["team_id"]
    api_key = setup["api_key"]

    # Create project
    proj_resp = await client.post(
        f"/api/v1/teams/{team_id}/projects",
        headers={"X-API-Key": api_key},
        json={"name": "Empty Project"},
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # Delete should succeed
    del_resp = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"X-API-Key": api_key},
    )
    assert del_resp.status_code == 204
