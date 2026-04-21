"""API key rotation endpoint.

Closes the "leaked key = wipe the team" post-launch follow-up from
SECURITY.md. Rotation is OWNER-only, audit-logged, and replaces the
old key atomically.
"""
import pytest

from tests.conftest import make_team, make_user


async def _bootstrap(client):
    team = await make_team(client)
    return team, {
        "X-API-Key": team["api_key"],
        "X-User-Id": team["_setup_user_id"],
    }


@pytest.mark.asyncio
async def test_rotate_returns_new_plaintext_key(client):
    team, headers = await _bootstrap(client)
    resp = await client.post(
        f"/api/v1/teams/{team['id']}/api-key/rotate",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["api_key"].startswith("adhed_")
    assert body["api_key"] != team["api_key"]  # actually new


@pytest.mark.asyncio
async def test_rotate_invalidates_old_key(client):
    team, headers = await _bootstrap(client)
    rotate = await client.post(
        f"/api/v1/teams/{team['id']}/api-key/rotate",
        headers=headers,
    )
    # Old key must no longer authenticate
    resp = await client.get(
        f"/api/v1/teams/{team['id']}/states",
        headers={"X-API-Key": team["api_key"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rotate_new_key_works(client):
    team, headers = await _bootstrap(client)
    rotate = await client.post(
        f"/api/v1/teams/{team['id']}/api-key/rotate",
        headers=headers,
    )
    new_key = rotate.json()["data"]["api_key"]
    # New key authenticates
    resp = await client.get(
        f"/api/v1/teams/{team['id']}/states",
        headers={"X-API-Key": new_key},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rotate_requires_owner(client):
    team, owner_headers = await _bootstrap(client)
    # Add a MEMBER user, try rotating as them
    member = await make_user(
        client, team["id"], team["api_key"],
        name="Kristen", email="k@example.com",
        as_user_id=team["_setup_user_id"],
    )
    member_headers = {"X-API-Key": team["api_key"], "X-User-Id": member["id"]}

    resp = await client.post(
        f"/api/v1/teams/{team['id']}/api-key/rotate",
        headers=member_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rotate_writes_audit_entry(client):
    team, headers = await _bootstrap(client)
    rotate = await client.post(
        f"/api/v1/teams/{team['id']}/api-key/rotate",
        headers=headers,
    )
    new_key = rotate.json()["data"]["api_key"]
    new_headers = {"X-API-Key": new_key, "X-User-Id": team["_setup_user_id"]}

    audit = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=new_headers,
        params={"entity_type": "team_api_key"},
    )
    entries = audit.json()["data"]
    assert len(entries) == 1
    assert entries[0]["action"] == "update"
    assert entries[0]["user_id"] == team["_setup_user_id"]
