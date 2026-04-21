import pytest

from taskstore.models.enums import StateType


async def bootstrap(client, name="Acme", key="acme", email="a@example.com"):
    """Bootstrap a team via /setup (first-team path, no auth required)."""
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": name,
            "team_key": key,
            "user_name": "Owner",
            "user_email": email,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_team_via_setup(client):
    """First team is created via /setup (owner + team in one shot)."""
    data = bootstrap_response = await bootstrap(client)
    assert data["team_name"] == "Acme"
    assert data["team_key"] == "ACME"
    assert data["api_key"].startswith("adhed_")


@pytest.mark.asyncio
async def test_create_second_team_requires_owner(client):
    """POST /teams requires an OWNER caller — see tests/test_team_creation_auth.py
    for the full auth matrix. This is just a smoke check."""
    first = await bootstrap(client)
    resp = await client.post(
        "/api/v1/teams",
        headers={"X-API-Key": first["api_key"], "X-User-Id": first["user_id"]},
        json={"name": "Second", "key": "SEC"},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["api_key"].startswith("adhed_")


@pytest.mark.asyncio
async def test_setup_seeds_default_states(client):
    data = await bootstrap(client, name="Seeded", key="seed")
    team_id = data["team_id"]
    api_key = data["api_key"]

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
    first = await bootstrap(client, name="First", key="dup")
    resp = await client.post(
        "/api/v1/teams",
        headers={"X-API-Key": first["api_key"], "X-User-Id": first["user_id"]},
        json={"name": "Second", "key": "dup"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_team(client):
    data = await bootstrap(client, name="Getter", key="get1")
    team_id = data["team_id"]
    api_key = data["api_key"]

    get_resp = await client.get(
        f"/api/v1/teams/{team_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_resp.status_code == 200
    fetched = get_resp.json()["data"]
    assert fetched["id"] == team_id
    assert fetched["name"] == "Getter"
    assert fetched["key"] == "GET1"
    # C2: api_key must not be in the GET response
    assert "api_key" not in fetched


@pytest.mark.asyncio
async def test_update_team_settings(client):
    data = await bootstrap(client, name="Updater", key="upd1")
    team_id = data["team_id"]
    api_key = data["api_key"]

    patch_resp = await client.patch(
        f"/api/v1/teams/{team_id}",
        headers={"X-API-Key": api_key, "X-User-Id": data["user_id"]},
        json={"settings": {"archive_days": 60, "triage_enabled": False}},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()["data"]
    assert updated["settings"]["archive_days"] == 60
    assert updated["settings"]["triage_enabled"] is False
