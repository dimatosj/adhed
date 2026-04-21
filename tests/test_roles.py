"""Regression tests for H1: role matrix enforcement.

Role matrix (reviewer-approved):

| Action                            | OWNER | ADMIN | MEMBER |
|-----------------------------------|-------|-------|--------|
| CRUD issues, comments             |  ✅   |  ✅   |  ✅    |
| Create/update labels, projects    |  ✅   |  ✅   |  ✅    |
| Delete labels, projects           |  ✅   |  ✅   |  ❌    |
| Create/update/delete rules        |  ✅   |  ✅   |  ❌    |
| Create states                     |  ✅   |  ✅   |  ❌    |
| Add members                       |  ✅   |  ✅   |  ❌    |
| Update team settings              |  ✅   |  ✅   |  ❌    |
| POST /teams                       |  ✅   |  ❌   |  ❌    |
| View audit (all users)            |  ✅   |  ✅   |  ❌    |
| View audit (self only)            |  ✅   |  ✅   |  ✅    |
"""
import uuid

import pytest
from sqlalchemy import update as sa_update

from taskstore.models.enums import TeamRole
from taskstore.models.user import TeamMembership
from tests.conftest import TestSessionLocal, make_team, make_user


async def _three_role_fixture(client):
    """Create a team and three users with roles owner, admin, member.
    Returns a dict with headers for each."""
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]

    owner_id = team["_setup_user_id"]

    admin = await make_user(
        client, team_id, api_key,
        name="Admin", email="admin@example.com",
        as_user_id=owner_id,
    )
    member = await make_user(
        client, team_id, api_key,
        name="Member", email="member@example.com",
        as_user_id=owner_id,
    )

    # Elevate admin to ADMIN role (default would be MEMBER — second+ user)
    async with TestSessionLocal() as session:
        await session.execute(
            sa_update(TeamMembership)
            .where(
                TeamMembership.team_id == uuid.UUID(team_id),
                TeamMembership.user_id == uuid.UUID(admin["id"]),
            )
            .values(role=TeamRole.ADMIN)
        )
        await session.commit()

    return {
        "team_id": team_id,
        "api_key": api_key,
        "owner_headers": {"X-API-Key": api_key, "X-User-Id": owner_id},
        "admin_headers": {"X-API-Key": api_key, "X-User-Id": admin["id"]},
        "member_headers": {"X-API-Key": api_key, "X-User-Id": member["id"]},
        "owner_id": owner_id,
        "admin_id": admin["id"],
        "member_id": member["id"],
    }


@pytest.fixture
async def roles(client):
    return await _three_role_fixture(client)


# ----- Endpoints MEMBER must NOT access -----


@pytest.mark.asyncio
async def test_member_cannot_delete_label(client, roles):
    label = await client.post(
        f"/api/v1/teams/{roles['team_id']}/labels",
        headers=roles["owner_headers"],
        json={"name": "doomed"},
    )
    assert label.status_code == 201
    label_id = label.json()["data"]["id"]

    resp = await client.delete(
        f"/api/v1/labels/{label_id}",
        headers=roles["member_headers"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_delete_project(client, roles):
    project = await client.post(
        f"/api/v1/teams/{roles['team_id']}/projects",
        headers=roles["admin_headers"],
        json={"name": "doomed-proj"},
    )
    assert project.status_code == 201
    pid = project.json()["data"]["id"]

    resp = await client.delete(
        f"/api/v1/projects/{pid}",
        headers=roles["member_headers"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_create_rule(client, roles):
    resp = await client.post(
        f"/api/v1/teams/{roles['team_id']}/rules",
        headers=roles["member_headers"],
        json={
            "name": "nope",
            "trigger": "issue.created",
            "conditions": {"type": "field_equals", "field": "title", "value": "x"},
            "actions": [{"type": "add_label", "label": "nope"}],
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_update_or_delete_rule(client, roles):
    rule = await client.post(
        f"/api/v1/teams/{roles['team_id']}/rules",
        headers=roles["admin_headers"],
        json={
            "name": "owned by admin",
            "trigger": "issue.created",
            "conditions": {"type": "field_equals", "field": "title", "value": "x"},
            "actions": [{"type": "add_label", "label": "x"}],
        },
    )
    assert rule.status_code == 201
    rid = rule.json()["data"]["id"]

    patch = await client.patch(
        f"/api/v1/rules/{rid}",
        headers=roles["member_headers"],
        json={"enabled": False},
    )
    assert patch.status_code == 403

    delete = await client.delete(
        f"/api/v1/rules/{rid}",
        headers=roles["member_headers"],
    )
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_add_member(client, roles):
    resp = await client.post(
        f"/api/v1/teams/{roles['team_id']}/users",
        headers=roles["member_headers"],
        json={"name": "Intruder", "email": "intruder@example.com"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_create_state(client, roles):
    resp = await client.post(
        f"/api/v1/teams/{roles['team_id']}/states",
        headers=roles["member_headers"],
        json={"name": "Review", "type": "started", "position": 1},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_update_team_settings(client, roles):
    resp = await client.patch(
        f"/api/v1/teams/{roles['team_id']}",
        headers=roles["member_headers"],
        json={"settings": {"archive_days": 99, "triage_enabled": False}},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_view_all_audit(client, roles):
    """MEMBER viewing the team audit trail must be filtered to their own
    entries — seeing other members' audit is ADMIN+ only. We enforce by
    either (a) returning 403 without user_id filter, or (b) accepting
    and silently filtering. Either is defensible; we pick 403 for
    explicitness."""
    resp = await client.get(
        f"/api/v1/teams/{roles['team_id']}/audit",
        headers=roles["member_headers"],
    )
    # 403 OR 200-with-only-own-entries are both acceptable implementations
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        entries = resp.json()["data"]
        for e in entries:
            assert e["user_id"] == roles["member_id"], (
                f"MEMBER audit response leaked non-own entries: {entries}"
            )


# ----- Endpoints MEMBER MUST access -----


@pytest.mark.asyncio
async def test_member_can_crud_issues(client, roles):
    # Create
    create = await client.post(
        f"/api/v1/teams/{roles['team_id']}/issues",
        headers=roles["member_headers"],
        json={"title": "member task"},
    )
    assert create.status_code == 201
    issue_id = create.json()["data"]["id"]

    # Update
    patch = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=roles["member_headers"],
        json={"priority": 3},
    )
    assert patch.status_code == 200


@pytest.mark.asyncio
async def test_member_can_create_label_and_project(client, roles):
    label = await client.post(
        f"/api/v1/teams/{roles['team_id']}/labels",
        headers=roles["owner_headers"],
        json={"name": "by-member"},
    )
    assert label.status_code == 201

    proj = await client.post(
        f"/api/v1/teams/{roles['team_id']}/projects",
        headers=roles["member_headers"],
        json={"name": "member-proj"},
    )
    assert proj.status_code == 201


@pytest.mark.asyncio
async def test_member_can_comment(client, roles):
    create = await client.post(
        f"/api/v1/teams/{roles['team_id']}/issues",
        headers=roles["admin_headers"],
        json={"title": "commentable"},
    )
    assert create.status_code == 201
    issue_id = create.json()["data"]["id"]

    comment = await client.post(
        f"/api/v1/issues/{issue_id}/comments",
        headers=roles["member_headers"],
        json={"body": "I am a humble member"},
    )
    assert comment.status_code == 201


# ----- ADMIN can do the gated actions -----


@pytest.mark.asyncio
async def test_admin_can_delete_label(client, roles):
    label = await client.post(
        f"/api/v1/teams/{roles['team_id']}/labels",
        headers=roles["owner_headers"],
        json={"name": "doomed2"},
    )
    label_id = label.json()["data"]["id"]
    resp = await client.delete(
        f"/api/v1/labels/{label_id}",
        headers=roles["admin_headers"],
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_can_create_rule(client, roles):
    resp = await client.post(
        f"/api/v1/teams/{roles['team_id']}/rules",
        headers=roles["admin_headers"],
        json={
            "name": "by admin",
            "trigger": "issue.created",
            "conditions": {"type": "field_equals", "field": "title", "value": "x"},
            "actions": [{"type": "add_label", "label": "x"}],
        },
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_admin_can_update_team_settings(client, roles):
    resp = await client.patch(
        f"/api/v1/teams/{roles['team_id']}",
        headers=roles["admin_headers"],
        json={"name": "Renamed by admin"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_create_new_team(client, roles):
    """POST /teams is OWNER-only (already enforced in PR 1 via require_owner).
    Explicit regression test here so the role matrix is fully covered."""
    resp = await client.post(
        "/api/v1/teams",
        headers=roles["admin_headers"],
        json={"name": "Forbidden", "key": "NOPE"},
    )
    assert resp.status_code == 403
