import pytest

from taskstore.models.enums import StateType


@pytest.mark.asyncio
async def test_create_team(client):
    resp = await client.post("/api/v1/teams", json={"name": "Acme", "key": "acme"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Acme"
    assert data["key"] == "ACME"
    assert data["api_key"].startswith("adhed_")
    assert data["settings"]["archive_days"] == 30
    assert data["settings"]["triage_enabled"] is True


@pytest.mark.asyncio
async def test_create_team_seeds_default_states(client):
    create_resp = await client.post("/api/v1/teams", json={"name": "Seeded", "key": "seed"})
    assert create_resp.status_code == 201
    team = create_resp.json()["data"]
    team_id = team["id"]
    api_key = team["api_key"]

    states_resp = await client.get(
        f"/api/v1/teams/{team_id}/states",
        headers={"X-API-Key": api_key},
    )
    assert states_resp.status_code == 200
    states = states_resp.json()["data"]
    assert len(states) == 6

    types = {s["type"] for s in states}
    expected_types = {
        StateType.TRIAGE.value,
        StateType.BACKLOG.value,
        StateType.UNSTARTED.value,
        StateType.STARTED.value,
        StateType.COMPLETED.value,
        StateType.CANCELED.value,
    }
    assert types == expected_types


@pytest.mark.asyncio
async def test_create_team_duplicate_key(client):
    await client.post("/api/v1/teams", json={"name": "First", "key": "dup"})
    resp = await client.post("/api/v1/teams", json={"name": "Second", "key": "dup"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_team(client):
    create_resp = await client.post("/api/v1/teams", json={"name": "Getter", "key": "get1"})
    assert create_resp.status_code == 201
    team = create_resp.json()["data"]
    team_id = team["id"]
    api_key = team["api_key"]

    get_resp = await client.get(
        f"/api/v1/teams/{team_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    fetched = get_resp.json()["data"]
    assert fetched["id"] == team_id
    assert fetched["name"] == "Getter"
    assert fetched["key"] == "GET1"


@pytest.mark.asyncio
async def test_update_team_settings(client):
    create_resp = await client.post("/api/v1/teams", json={"name": "Updater", "key": "upd1"})
    assert create_resp.status_code == 201
    team = create_resp.json()["data"]
    team_id = team["id"]
    api_key = team["api_key"]

    patch_resp = await client.patch(
        f"/api/v1/teams/{team_id}",
        headers={"X-API-Key": api_key},
        json={"settings": {"archive_days": 60, "triage_enabled": False}},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()["data"]
    assert updated["settings"]["archive_days"] == 60
    assert updated["settings"]["triage_enabled"] is False
