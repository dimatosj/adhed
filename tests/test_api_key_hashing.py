"""Regression tests for C2: API keys are stored as SHA-256 hashes,
not plaintext, and are only returned at creation time.
"""

import pytest
from sqlalchemy import select

from taskstore.models.team import Team
from tests.conftest import TestSessionLocal


async def _bootstrap(client, name="Secret", key="SEC", email="s@example.com"):
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": name,
            "team_key": key,
            "user_name": "Owner",
            "user_email": email,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_get_team_does_not_return_api_key(client):
    """GET /teams/{id} must not echo the API key. A team member reading
    their own team should not be able to exfiltrate the master key."""
    bootstrap = await _bootstrap(client)
    get_resp = await client.get(
        f"/api/v1/teams/{bootstrap['team_id']}",
        headers={"X-API-Key": bootstrap["api_key"]},
    )
    assert get_resp.status_code == 200
    body = get_resp.json()["data"]
    assert "api_key" not in body, (
        f"GET /teams must not echo api_key; got: {body}"
    )


@pytest.mark.asyncio
async def test_patch_team_does_not_return_api_key(client):
    bootstrap = await _bootstrap(client, name="Patchy", key="PAT")
    patch_resp = await client.patch(
        f"/api/v1/teams/{bootstrap['team_id']}",
        headers={
            "X-API-Key": bootstrap["api_key"],
            "X-User-Id": bootstrap["user_id"],
        },
        json={"name": "Patched"},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()["data"]
    assert "api_key" not in body


@pytest.mark.asyncio
async def test_create_team_returns_api_key_once(client):
    """POST /teams (authed as OWNER) is the only path that returns
    the plaintext key for a subsequently-created team."""
    first = await _bootstrap(client)
    resp = await client.post(
        "/api/v1/teams",
        headers={
            "X-API-Key": first["api_key"],
            "X-User-Id": first["user_id"],
        },
        json={"name": "Fresh", "key": "FR"},
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["api_key"].startswith("adhed_"), body


@pytest.mark.asyncio
async def test_api_key_not_stored_plaintext_in_db(client):
    """The DB column must store a hash, not the plaintext key."""
    bootstrap = await _bootstrap(client, name="NoPlaintext", key="NP")
    plaintext = bootstrap["api_key"]

    async with TestSessionLocal() as session:
        row = await session.execute(
            select(Team).where(Team.name == "NoPlaintext")
        )
        team = row.scalar_one()
        # The stored value, whatever its attribute name, must NOT equal
        # the plaintext key that was returned to the client.
        stored = getattr(team, "api_key_hash", None) or getattr(team, "api_key", None)
        assert stored is not None, "Team must have a key column"
        assert stored != plaintext, (
            "API key stored as plaintext — must be hashed. "
            f"stored={stored!r}, plaintext={plaintext!r}"
        )


@pytest.mark.asyncio
async def test_auth_still_works_with_hashed_key(client):
    """After hashing, the returned plaintext key must still authenticate.
    (Otherwise we've broken the whole auth system.)"""
    bootstrap = await _bootstrap(client, name="AuthCheck", key="AU")
    states_resp = await client.get(
        f"/api/v1/teams/{bootstrap['team_id']}/states",
        headers={"X-API-Key": bootstrap["api_key"]},
    )
    assert states_resp.status_code == 200, states_resp.text


@pytest.mark.asyncio
async def test_setup_response_returns_plaintext_key(client):
    """/setup is the bootstrap path and must return the plaintext key
    so the caller can record it."""
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": "Home",
            "team_key": "HOME",
            "user_name": "Jane",
            "user_email": "jane@example.com",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["api_key"].startswith("adhed_")

    # And that key should authenticate
    states_resp = await client.get(
        f"/api/v1/teams/{body['team_id']}/states",
        headers={"X-API-Key": body["api_key"]},
    )
    assert states_resp.status_code == 200
