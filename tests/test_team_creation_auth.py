"""Regression tests for C1 + S3.

C1: POST /api/v1/teams must require an OWNER-role caller. /setup
remains the only unauthenticated path and refuses to run once any
team exists.

S3: UserCreate must not accept a `role` field. A caller must not
be able to mint an OWNER membership via POST /teams/{id}/users.
"""

import pytest


async def _setup_first_team(client, email="founder@x.test"):
    """Use /setup to create the first team + owner user."""
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": "Initial",
            "team_key": "INIT",
            "user_name": "Founder",
            "user_email": email,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_post_teams_unauthenticated_rejected(client):
    """POST /teams with no headers must be 401."""
    # Bootstrap a team via setup first so /teams isn't the first team path
    await _setup_first_team(client)

    resp = await client.post("/api/v1/teams", json={"name": "X", "key": "X"})
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_post_teams_as_member_rejected(client):
    """A non-owner member with a valid API key must still be 403."""
    first = await _setup_first_team(client)
    api_key = first["api_key"]
    team_id = first["team_id"]

    # Add a second user (role not accepted from request body)
    member_resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": "Member", "email": "m@x.test"},
    )
    assert member_resp.status_code == 201
    member_id = member_resp.json()["data"]["id"]
    # Second user defaults to MEMBER role (owner was the first)
    assert member_resp.json()["data"]["role"] == "member"

    # Member tries to create a new team
    resp = await client.post(
        "/api/v1/teams",
        headers={"X-API-Key": api_key, "X-User-Id": member_id},
        json={"name": "X", "key": "X"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_post_teams_as_owner_succeeds(client):
    """An OWNER of an existing team can create additional teams."""
    first = await _setup_first_team(client)
    resp = await client.post(
        "/api/v1/teams",
        headers={"X-API-Key": first["api_key"], "X-User-Id": first["user_id"]},
        json={"name": "Second", "key": "SEC"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["name"] == "Second"
    assert resp.json()["data"]["api_key"].startswith("adhed_")


@pytest.mark.asyncio
async def test_setup_refuses_when_teams_exist(client):
    """/setup is a one-shot — second call is 409 even with different data."""
    await _setup_first_team(client)
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": "Second",
            "team_key": "SEC",
            "user_name": "X",
            "user_email": "x@x.test",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_user_create_rejects_role_field(client):
    """S3: UserCreate must not accept a client-supplied role, or an
    attacker could mint themselves as OWNER. Either schema rejects the
    field (422) or the server must ignore it entirely."""
    first = await _setup_first_team(client)
    team_id = first["team_id"]
    api_key = first["api_key"]

    resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={
            "name": "Sneaky",
            "email": "sneaky@x.test",
            "role": "owner",  # must not elevate
        },
    )
    # Either 422 (schema rejects extra) or 201 with role != owner.
    if resp.status_code == 201:
        assert resp.json()["data"]["role"] != "owner", (
            "UserCreate accepted client-supplied role — privilege escalation!"
        )
    else:
        assert resp.status_code == 422, resp.text
