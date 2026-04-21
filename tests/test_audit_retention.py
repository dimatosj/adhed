"""DELETE /api/v1/teams/{id}/audit — prune old audit entries.

OWNER-only. Accepts ?before=<datetime> (required) and returns the
count of deleted rows. Prevents unbounded audit-table growth over
the lifetime of a team.
"""
from datetime import timedelta

import pytest

from taskstore.utils.time import now_utc
from tests.conftest import make_team, make_user


async def _bootstrap(client):
    team = await make_team(client)
    return team, {
        "X-API-Key": team["api_key"],
        "X-User-Id": team["_setup_user_id"],
    }


@pytest.mark.asyncio
async def test_delete_audit_before_requires_owner(client):
    team, owner_headers = await _bootstrap(client)
    member = await make_user(
        client, team["id"], team["api_key"],
        name="M", email="m@x.test",
        as_user_id=team["_setup_user_id"],
    )
    member_headers = {"X-API-Key": team["api_key"], "X-User-Id": member["id"]}

    resp = await client.delete(
        f"/api/v1/teams/{team['id']}/audit",
        headers=member_headers,
        params={"before": now_utc().isoformat()},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_audit_before_requires_before_param(client):
    team, headers = await _bootstrap(client)
    resp = await client.delete(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
    )
    # Missing required query param → 422 from FastAPI
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_audit_removes_only_entries_before_cutoff(client):
    team, headers = await _bootstrap(client)

    # Generate some audit entries by adding a user (creates a membership
    # audit entry). Then sleep a beat and create another.
    first = await client.post(
        f"/api/v1/teams/{team['id']}/users",
        headers=headers,
        json={"name": "A", "email": "a@x.test"},
    )
    assert first.status_code == 201

    # Grab "now" as cutoff
    cutoff = now_utc()

    # Small delta so the second entry is strictly after the cutoff
    import asyncio
    await asyncio.sleep(0.05)

    second = await client.post(
        f"/api/v1/teams/{team['id']}/users",
        headers=headers,
        json={"name": "B", "email": "b@x.test"},
    )
    assert second.status_code == 201

    # Confirm 2 audit entries exist before pruning
    pre = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "membership"},
    )
    assert len(pre.json()["data"]) == 2

    # Prune everything before the cutoff — only the first entry
    prune = await client.delete(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"before": cutoff.isoformat()},
    )
    assert prune.status_code == 200
    assert prune.json()["data"]["deleted"] == 1

    # Only the second entry remains
    post = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "membership"},
    )
    assert len(post.json()["data"]) == 1


@pytest.mark.asyncio
async def test_delete_audit_returns_zero_when_no_matches(client):
    team, headers = await _bootstrap(client)
    # Cutoff in the far past — nothing to delete
    ancient = now_utc() - timedelta(days=365 * 10)
    resp = await client.delete(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"before": ancient.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] == 0


@pytest.mark.asyncio
async def test_delete_audit_scopes_to_authed_team(client):
    """Cross-tenant: team A's OWNER pruning team B's audit must 403."""
    team_a, headers_a = await _bootstrap(client)
    # Can't test this with only _bootstrap (it exhausts /setup). Use
    # verified_team_owner's path-team_id check — non-matching team_id
    # returns 403.
    resp = await client.delete(
        "/api/v1/teams/00000000-0000-0000-0000-000000000000/audit",
        headers=headers_a,
        params={"before": now_utc().isoformat()},
    )
    assert resp.status_code == 403
