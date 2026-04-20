import pytest


async def make_team(client, name="Acme", key="acme"):
    resp = await client.post("/api/v1/teams", json={"name": name, "key": key})
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_create_label(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    resp = await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
        json={"name": "Bug", "color": "#ff0000"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Bug"
    assert data["color"] == "#ff0000"
    assert data["team_id"] == team_id


@pytest.mark.asyncio
async def test_list_labels(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
        json={"name": "Bug"},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
        json={"name": "Feature"},
    )

    resp = await client.get(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_duplicate_label_name(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
        json={"name": "Bug"},
    )
    resp = await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
        json={"name": "Bug"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_label(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    create_resp = await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
        json={"name": "Bug", "color": "#ff0000"},
    )
    label_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/labels/{label_id}",
        headers={"X-API-Key": api_key},
        json={"color": "#00ff00"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["color"] == "#00ff00"
    assert data["name"] == "Bug"


@pytest.mark.asyncio
async def test_delete_label(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    create_resp = await client.post(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
        json={"name": "Bug"},
    )
    label_id = create_resp.json()["data"]["id"]

    del_resp = await client.delete(
        f"/api/v1/labels/{label_id}",
        headers={"X-API-Key": api_key},
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
    )
    assert len(list_resp.json()["data"]) == 0
