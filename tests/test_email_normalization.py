"""Q12: EmailStr validation + case-insensitive dedup.

Previously `email: str` accepted `"not an email"` and
`John@X.com` vs `john@x.com` created two separate rows despite
looking like the same user to humans. This PR:
- Rejects malformed emails at the schema layer (422)
- Lowercases at write time so the unique constraint works as
  expected.
"""
import pytest

from tests.conftest import make_team


async def _bootstrap(client):
    team = await make_team(client)
    return team, {
        "X-API-Key": team["api_key"],
        "X-User-Id": team["_setup_user_id"],
    }


@pytest.mark.asyncio
async def test_malformed_email_rejected(client):
    team, headers = await _bootstrap(client)
    resp = await client.post(
        f"/api/v1/teams/{team['id']}/users",
        headers=headers,
        json={"name": "Bad", "email": "not-an-email"},
    )
    assert resp.status_code == 422
    body = resp.json()
    # Envelope shape (PR #3)
    assert body["data"] is None
    assert any("email" in e["message"].lower() for e in body["errors"])


@pytest.mark.asyncio
async def test_same_email_different_case_dedupes(client):
    team, headers = await _bootstrap(client)
    first = await client.post(
        f"/api/v1/teams/{team['id']}/users",
        headers=headers,
        json={"name": "Alice", "email": "alice@example.com"},
    )
    assert first.status_code == 201
    alice_id = first.json()["data"]["id"]

    # Same email with different capitalization should resolve to the
    # same user, not create a duplicate.
    second = await client.post(
        f"/api/v1/teams/{team['id']}/users",
        headers=headers,
        json={"name": "Alice", "email": "Alice@Example.COM"},
    )
    assert second.status_code == 201
    assert second.json()["data"]["id"] == alice_id, (
        f"Case-different email should dedupe: {second.json()}"
    )


@pytest.mark.asyncio
async def test_email_stored_lowercase(client):
    team, headers = await _bootstrap(client)
    resp = await client.post(
        f"/api/v1/teams/{team['id']}/users",
        headers=headers,
        json={"name": "Bob", "email": "BOB@Example.com"},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_setup_rejects_malformed_email(client):
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": "X",
            "team_key": "X",
            "user_name": "x",
            "user_email": "not-an-email",
        },
    )
    assert resp.status_code == 422
