"""PATCH /teams/{id}/members/{user_id} — role-change endpoint.

OWNER-only. Prevents demoting the last OWNER (otherwise the team
becomes unmanageable). Audit-logged as entity_type=membership.
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
async def test_owner_promotes_member_to_admin(client):
    team, headers = await _bootstrap(client)
    member = await make_user(
        client, team["id"], team["api_key"],
        name="Alex", email="a@x.test",
        as_user_id=team["_setup_user_id"],
    )
    assert member["role"] == "member"

    resp = await client.patch(
        f"/api/v1/teams/{team['id']}/members/{member['id']}",
        headers=headers,
        json={"role": "admin"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["role"] == "admin"


@pytest.mark.asyncio
async def test_non_owner_cannot_change_roles(client):
    team, owner_headers = await _bootstrap(client)
    member = await make_user(
        client, team["id"], team["api_key"],
        name="Alex", email="a@x.test",
        as_user_id=team["_setup_user_id"],
    )
    member_headers = {"X-API-Key": team["api_key"], "X-User-Id": member["id"]}

    resp = await client.patch(
        f"/api/v1/teams/{team['id']}/members/{member['id']}",
        headers=member_headers,
        json={"role": "admin"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_demote_last_owner(client):
    team, headers = await _bootstrap(client)
    # The setup user is the ONLY owner. Demoting them would leave the
    # team with no owner — must be blocked.
    resp = await client.patch(
        f"/api/v1/teams/{team['id']}/members/{team['_setup_user_id']}",
        headers=headers,
        json={"role": "member"},
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert "last owner" in body["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_can_demote_owner_when_another_owner_exists(client):
    team, headers = await _bootstrap(client)
    second = await make_user(
        client, team["id"], team["api_key"],
        name="Bea", email="b@x.test",
        as_user_id=team["_setup_user_id"],
    )
    # Promote bea to owner
    promote = await client.patch(
        f"/api/v1/teams/{team['id']}/members/{second['id']}",
        headers=headers,
        json={"role": "owner"},
    )
    assert promote.status_code == 200

    # Now the original owner can step down to admin
    demote = await client.patch(
        f"/api/v1/teams/{team['id']}/members/{team['_setup_user_id']}",
        headers=headers,
        json={"role": "admin"},
    )
    assert demote.status_code == 200, demote.text


@pytest.mark.asyncio
async def test_role_change_is_audited(client):
    team, headers = await _bootstrap(client)
    member = await make_user(
        client, team["id"], team["api_key"],
        name="Alex", email="a@x.test",
        as_user_id=team["_setup_user_id"],
    )
    await client.patch(
        f"/api/v1/teams/{team['id']}/members/{member['id']}",
        headers=headers,
        json={"role": "admin"},
    )

    audit = await client.get(
        f"/api/v1/teams/{team['id']}/audit",
        headers=headers,
        params={"entity_type": "membership", "action": "update"},
    )
    entries = audit.json()["data"]
    assert len(entries) == 1
    assert entries[0]["entity_id"] == member["id"]
    assert entries[0]["user_id"] == team["_setup_user_id"]


@pytest.mark.asyncio
async def test_change_role_for_nonexistent_member_404s(client):
    team, headers = await _bootstrap(client)
    resp = await client.patch(
        f"/api/v1/teams/{team['id']}/members/00000000-0000-0000-0000-000000000000",
        headers=headers,
        json={"role": "admin"},
    )
    assert resp.status_code == 404
