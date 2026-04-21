"""Regression tests for S2: cross-tenant reference injection.

FK constraints on Issue are global (project_id -> projects.id, not
projects where team_id=X), so without explicit validation an API-key
holder for team A could create an issue in A referencing team B's
state/project/parent/label. Every FK on an Issue write must be
verified to belong to the authed team.
"""

import uuid

import pytest


async def _bootstrap_team_via_setup(client, name, key, email):
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": name,
            "team_key": key,
            "user_name": name + " Owner",
            "user_email": email,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _second_team_as_owner(client, owner_ctx, name, key):
    """Create an additional team authed as an existing team's OWNER."""
    resp = await client.post(
        "/api/v1/teams",
        headers={
            "X-API-Key": owner_ctx["api_key"],
            "X-User-Id": owner_ctx["user_id"],
        },
        json={"name": name, "key": key},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _add_owner_to_team(client, team_id, owner_api_key, name, email):
    """Create a user and manually elevate to OWNER (bypassing API)
    so they can act as the team's owner in tests."""
    from sqlalchemy import update as sa_update
    from taskstore.models.enums import TeamRole
    from taskstore.models.user import TeamMembership
    from tests.conftest import TestSessionLocal

    user_resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": owner_api_key},
        json={"name": name, "email": email},
    )
    assert user_resp.status_code == 201
    user = user_resp.json()["data"]
    async with TestSessionLocal() as session:
        await session.execute(
            sa_update(TeamMembership)
            .where(
                TeamMembership.team_id == uuid.UUID(team_id),
                TeamMembership.user_id == uuid.UUID(user["id"]),
            )
            .values(role=TeamRole.OWNER)
        )
        await session.commit()
    return user


async def _fetch_states(client, team_id, api_key):
    states_resp = await client.get(
        f"/api/v1/teams/{team_id}/states",
        headers={"X-API-Key": api_key},
    )
    assert states_resp.status_code == 200
    return {s["type"]: s for s in states_resp.json()["data"]}


@pytest.fixture
async def two_teams(client):
    # Team A via /setup — creates team + owner in one shot
    a_setup = await _bootstrap_team_via_setup(
        client, "TeamA", "TEAMA", "a@x.test"
    )
    a_states = await _fetch_states(client, a_setup["team_id"], a_setup["api_key"])
    a = {
        "team_id": a_setup["team_id"],
        "api_key": a_setup["api_key"],
        "user_id": a_setup["user_id"],
        "headers": {
            "X-API-Key": a_setup["api_key"],
            "X-User-Id": a_setup["user_id"],
        },
        "states": a_states,
    }

    # Team B via POST /teams authed as A's owner
    b_team = await _second_team_as_owner(client, a, "TeamB", "TEAMB")
    # Add a user to team B and elevate to owner so B can act independently
    b_owner = await _add_owner_to_team(
        client, b_team["id"], b_team["api_key"], "B Owner", "b@x.test"
    )
    b_states = await _fetch_states(client, b_team["id"], b_team["api_key"])
    b = {
        "team_id": b_team["id"],
        "api_key": b_team["api_key"],
        "user_id": b_owner["id"],
        "headers": {
            "X-API-Key": b_team["api_key"],
            "X-User-Id": b_owner["id"],
        },
        "states": b_states,
    }
    return a, b


@pytest.mark.asyncio
async def test_create_issue_rejects_cross_tenant_state_id(client, two_teams):
    a, b = two_teams
    # Team A tries to create an issue pointing at team B's state
    resp = await client.post(
        f"/api/v1/teams/{a['team_id']}/issues",
        headers=a["headers"],
        json={"title": "x", "state_id": b["states"]["triage"]["id"]},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_issue_rejects_cross_tenant_project_id(client, two_teams):
    a, b = two_teams
    # Team B creates a project, team A tries to reference it
    proj_resp = await client.post(
        f"/api/v1/teams/{b['team_id']}/projects",
        headers=b["headers"],
        json={"name": "B project"},
    )
    assert proj_resp.status_code == 201
    b_project_id = proj_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/teams/{a['team_id']}/issues",
        headers=a["headers"],
        json={"title": "x", "project_id": b_project_id},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_issue_rejects_cross_tenant_parent_id(client, two_teams):
    a, b = two_teams
    # Team B creates an issue; team A tries to parent under it
    parent_resp = await client.post(
        f"/api/v1/teams/{b['team_id']}/issues",
        headers=b["headers"],
        json={"title": "B parent"},
    )
    assert parent_resp.status_code == 201
    b_issue_id = parent_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/teams/{a['team_id']}/issues",
        headers=a["headers"],
        json={"title": "A child", "parent_id": b_issue_id},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_issue_rejects_cross_tenant_label_id(client, two_teams):
    a, b = two_teams
    label_resp = await client.post(
        f"/api/v1/teams/{b['team_id']}/labels",
        headers={"X-API-Key": b["api_key"]},
        json={"name": "b-only"},
    )
    assert label_resp.status_code == 201
    b_label_id = label_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/teams/{a['team_id']}/issues",
        headers=a["headers"],
        json={"title": "x", "label_ids": [b_label_id]},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_issue_rejects_non_member_assignee(client, two_teams):
    a, b = two_teams
    # Team A tries to assign an issue to team B's user (not a member of A)
    resp = await client.post(
        f"/api/v1/teams/{a['team_id']}/issues",
        headers=a["headers"],
        json={"title": "x", "assignee_id": b["user_id"]},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_update_issue_rejects_cross_tenant_state_id(client, two_teams):
    a, b = two_teams
    # Create a legitimate issue in team A
    create_resp = await client.post(
        f"/api/v1/teams/{a['team_id']}/issues",
        headers=a["headers"],
        json={"title": "legit"},
    )
    assert create_resp.status_code == 201
    issue_id = create_resp.json()["data"]["id"]

    # Try to move it to team B's state
    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=a["headers"],
        json={"state_id": b["states"]["started"]["id"]},
    )
    assert patch_resp.status_code == 422, patch_resp.text


@pytest.mark.asyncio
async def test_create_issue_same_team_references_succeed(client, two_teams):
    """Sanity check: references to same-team resources continue to work."""
    a, _b = two_teams
    # Same-team state + same-team assignee should succeed
    resp = await client.post(
        f"/api/v1/teams/{a['team_id']}/issues",
        headers=a["headers"],
        json={
            "title": "same team",
            "state_id": a["states"]["triage"]["id"],
            "assignee_id": a["user_id"],
        },
    )
    assert resp.status_code == 201, resp.text
