"""Regression tests for Q4 (uniform error envelope) and S5 (no enum leaks).

Every response — success or error — is wrapped in the same Envelope
shape: `{"data": ..., "meta": ..., "errors": [...], "warnings": []}`.
Clients can parse one shape for everything.

Error details do not leak internal enum member paths (e.g.
`StateType.TRIAGE`) or internal schema names to the client.
"""
import pytest

from tests.conftest import make_team


async def _setup(client):
    team = await make_team(client)
    return team, {"X-API-Key": team["api_key"], "X-User-Id": team["_setup_user_id"]}


@pytest.mark.asyncio
async def test_404_error_is_envelope(client):
    team, headers = await _setup(client)
    # Non-existent issue
    resp = await client.get(
        "/api/v1/issues/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404
    body = resp.json()
    # Envelope keys present
    assert "data" in body
    assert "errors" in body
    assert "warnings" in body
    assert body["data"] is None
    assert len(body["errors"]) >= 1
    assert "not found" in body["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_403_forbidden_is_envelope(client):
    team, headers = await _setup(client)
    # Team A's key hitting a fake team id → 403 via verified_team
    resp = await client.get(
        "/api/v1/teams/00000000-0000-0000-0000-000000000000/issues",
        headers=headers,
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["data"] is None
    assert body["errors"][0]["message"].lower() in (
        "forbidden", "insufficient role"
    )


@pytest.mark.asyncio
async def test_401_unauthenticated_is_envelope(client):
    resp = await client.get("/api/v1/teams/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401
    body = resp.json()
    assert body["data"] is None
    assert "errors" in body
    assert body["errors"][0]["message"]  # non-empty


@pytest.mark.asyncio
async def test_422_validation_is_envelope(client):
    # Pydantic body validation failure: missing required fields on /setup
    resp = await client.post("/api/v1/setup", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["data"] is None
    assert "errors" in body
    assert len(body["errors"]) >= 1


@pytest.mark.asyncio
async def test_409_conflict_is_envelope(client):
    # /setup twice → 409 "Already set up"
    await client.post(
        "/api/v1/setup",
        json={
            "team_name": "First",
            "team_key": "FIRST",
            "user_name": "a",
            "user_email": "a@example.com",
        },
    )
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": "Second",
            "team_key": "SECOND",
            "user_name": "b",
            "user_email": "b@example.com",
        },
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["data"] is None
    assert body["errors"][0]["message"] == "Already set up"


@pytest.mark.asyncio
async def test_state_transition_error_does_not_leak_enum(client):
    """S5: invalid state transition error must not include Python enum
    member paths like 'StateType.TRIAGE'. Log the enum detail server-
    side; give the client a clean message."""
    team, headers = await _setup(client)
    # Create an issue (defaults to triage)
    create = await client.post(
        f"/api/v1/teams/{team['id']}/issues",
        headers=headers,
        json={"title": "x"},
    )
    assert create.status_code == 201
    issue_id = create.json()["data"]["id"]

    # Get states
    states_resp = await client.get(
        f"/api/v1/teams/{team['id']}/states",
        headers=headers,
    )
    states = {s["type"]: s for s in states_resp.json()["data"]}

    # TRIAGE → STARTED is invalid (must go via backlog/unstarted)
    patch = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"state_id": states["completed"]["id"]},
    )
    assert patch.status_code == 422
    body = patch.json()
    msg = body["errors"][0]["message"]
    # Clean user-facing message — no Python enum repr
    assert "StateType." not in msg, (
        f"Error message leaks Python enum path: {msg!r}"
    )


@pytest.mark.asyncio
async def test_success_still_uses_envelope(client):
    """Sanity: success responses keep the existing envelope shape."""
    team, headers = await _setup(client)
    resp = await client.get(
        f"/api/v1/teams/{team['id']}/issues",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body and "errors" in body
    assert isinstance(body["data"], list)
    assert body["errors"] == []
