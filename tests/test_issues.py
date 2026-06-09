import pytest

from taskstore.models.enums import StateType
from tests.conftest import get_states_by_type, make_team


@pytest.fixture
async def setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    user_id = team["_setup_user_id"]
    headers = {"X-API-Key": api_key, "X-User-Id": user_id}
    states = await get_states_by_type(client, team_id, api_key)
    return {
        "team": team,
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
        "states": states,
    }


@pytest.mark.asyncio
async def test_create_issue(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Fix login bug", "priority": 2},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["title"] == "Fix login bug"
    assert data["priority"] == 2
    assert data["type"] == "task"
    assert data["created_by"] == setup["user_id"]


@pytest.mark.asyncio
async def test_create_issue_defaults_to_triage(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Team has triage_enabled=True by default
    resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Triage me"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["state"]["type"] == StateType.TRIAGE.value
    assert data["state"]["id"] == states["triage"]["id"]


@pytest.mark.asyncio
async def test_get_issue(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    api_key = setup["api_key"]

    create_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Get me", "description": "A description", "priority": 3},
    )
    assert create_resp.status_code == 201
    issue_id = create_resp.json()["data"]["id"]

    get_resp = await client.get(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["id"] == issue_id
    assert data["title"] == "Get me"
    assert data["description"] == "A description"
    assert data["priority"] == 3
    assert data["type"] == "task"
    assert data["team_id"] == team_id
    assert data["created_by"] == setup["user_id"]
    assert data["state"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
    assert data["archived_at"] is None
    assert data["labels"] == []


@pytest.mark.asyncio
async def test_update_issue(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    create_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Old title", "priority": 1},
    )
    assert create_resp.status_code == 201
    issue_id = create_resp.json()["data"]["id"]

    patch_resp = await client.patch(
        f"/api/v1/issues/{issue_id}",
        headers=headers,
        json={"title": "New title", "priority": 5},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()["data"]
    assert data["title"] == "New title"
    assert data["priority"] == 5


@pytest.mark.asyncio
async def test_list_issues_filter_by_state_type(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Create an issue in triage (default)
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Triage issue"},
    )

    # Create an issue in started state
    started_state_id = states["started"]["id"]
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Started issue", "state_id": started_state_id},
    )

    # Create an issue in completed state
    completed_state_id = states["completed"]["id"]
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Done issue", "state_id": completed_state_id},
    )

    # Filter by started only
    resp = await client.get(
        f"/api/v1/teams/{team_id}/issues",
        headers={"X-API-Key": setup["api_key"]},
        params={"state_type": "started"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["title"] == "Started issue"

    # Filter by started,completed
    resp = await client.get(
        f"/api/v1/teams/{team_id}/issues",
        headers={"X-API-Key": setup["api_key"]},
        params={"state_type": "started,completed"},
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_list_issues_full_text_search(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Call the dentist"},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Buy groceries"},
    )

    resp = await client.get(
        f"/api/v1/teams/{team_id}/issues",
        headers={"X-API-Key": setup["api_key"]},
        params={"title_search": "dentist"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["title"] == "Call the dentist"


@pytest.mark.asyncio
async def test_create_subtask(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    # Create parent
    parent_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent task"},
    )
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["data"]["id"]

    # Create child
    child_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Child task", "parent_id": parent_id},
    )
    assert child_resp.status_code == 201
    child_data = child_resp.json()["data"]
    assert child_data["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_create_subtask_with_position(client, setup):
    """Subtasks can be created with explicit position for ordering."""
    headers = setup["headers"]
    team_id = setup["team_id"]

    # Create parent
    parent_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        json={"title": "Parent task"},
        headers=headers,
    )
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["data"]["id"]

    # Create children with positions
    for i, title in enumerate(
        ["Step 1: Buy parts", "Step 2: Turn off water", "Step 3: Replace washer"], start=1
    ):
        resp = await client.post(
            f"/api/v1/teams/{team_id}/issues",
            json={"title": title, "parent_id": parent_id, "position": i},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["position"] == i

    # List children — should be ordered by position
    list_resp = await client.get(
        f"/api/v1/teams/{team_id}/issues?parent_id={parent_id}&sort=position&order=asc",
        headers=headers,
    )
    assert list_resp.status_code == 200
    children = list_resp.json()["data"]
    assert len(children) == 3
    assert children[0]["title"] == "Step 1: Buy parts"
    assert children[1]["title"] == "Step 2: Turn off water"
    assert children[2]["title"] == "Step 3: Replace washer"


@pytest.mark.asyncio
async def test_delete_issue_with_active_children_fails(client, setup):
    headers = setup["headers"]
    team_id = setup["team_id"]

    # Create parent
    parent_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent"},
    )
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["data"]["id"]

    # Create child (defaults to triage state — active)
    child_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Child", "parent_id": parent_id},
    )
    assert child_resp.status_code == 201

    # Attempt to delete parent should fail with 409
    del_resp = await client.delete(
        f"/api/v1/issues/{parent_id}",
        headers=headers,
    )
    assert del_resp.status_code == 409


@pytest.mark.asyncio
async def test_update_issue_reparent_to_uuid(client, setup):
    """PATCH parent_id with a UUID re-parents a top-level issue under it."""
    headers = setup["headers"]
    team_id = setup["team_id"]

    # Parent A + a child already under A
    parent_a = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent A"},
    )
    assert parent_a.status_code == 201
    a_id = parent_a.json()["data"]["id"]

    child = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Existing child", "parent_id": a_id},
    )
    assert child.status_code == 201

    # Top-level issue X
    x_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Issue X"},
    )
    assert x_resp.status_code == 201
    x_id = x_resp.json()["data"]["id"]
    assert x_resp.json()["data"]["parent_id"] is None

    # Re-parent X under A
    patch_resp = await client.patch(
        f"/api/v1/issues/{x_id}",
        headers=headers,
        json={"parent_id": a_id},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["data"]["parent_id"] == a_id

    # GET confirms it persisted
    get_resp = await client.get(f"/api/v1/issues/{x_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["parent_id"] == a_id


@pytest.mark.asyncio
async def test_update_issue_move_between_parents(client, setup):
    """PATCH parent_id moves a child from one parent to another."""
    headers = setup["headers"]
    team_id = setup["team_id"]

    parent_a = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent A"},
    )
    assert parent_a.status_code == 201
    a_id = parent_a.json()["data"]["id"]

    parent_b = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent B"},
    )
    assert parent_b.status_code == 201
    b_id = parent_b.json()["data"]["id"]

    child_c = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Child C", "parent_id": a_id},
    )
    assert child_c.status_code == 201
    c_id = child_c.json()["data"]["id"]

    patch_resp = await client.patch(
        f"/api/v1/issues/{c_id}",
        headers=headers,
        json={"parent_id": b_id},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["data"]["parent_id"] == b_id


@pytest.mark.asyncio
async def test_update_issue_clear_parent_to_top_level(client, setup):
    """PATCH parent_id=null clears a child to top-level (explicit null
    survives exclude_unset) and advances updated_at."""
    headers = setup["headers"]
    team_id = setup["team_id"]

    parent_a = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent A"},
    )
    assert parent_a.status_code == 201
    a_id = parent_a.json()["data"]["id"]

    child = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Child", "parent_id": a_id},
    )
    assert child.status_code == 201
    child_id = child.json()["data"]["id"]
    before_updated_at = child.json()["data"]["updated_at"]

    patch_resp = await client.patch(
        f"/api/v1/issues/{child_id}",
        headers=headers,
        json={"parent_id": None},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    data = patch_resp.json()["data"]
    assert data["parent_id"] is None
    assert data["updated_at"] > before_updated_at


@pytest.mark.asyncio
async def test_update_issue_omitted_parent_id_leaves_unchanged(client, setup):
    """PATCH without parent_id must not disturb an existing parent."""
    headers = setup["headers"]
    team_id = setup["team_id"]

    parent_a = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Parent A"},
    )
    assert parent_a.status_code == 201
    a_id = parent_a.json()["data"]["id"]

    child = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Child", "parent_id": a_id},
    )
    assert child.status_code == 201
    child_id = child.json()["data"]["id"]

    patch_resp = await client.patch(
        f"/api/v1/issues/{child_id}",
        headers=headers,
        json={"title": "x"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["data"]["parent_id"] == a_id


@pytest.mark.asyncio
async def test_update_issue_self_parent_rejected(client, setup):
    """An issue cannot be made its own parent."""
    headers = setup["headers"]
    team_id = setup["team_id"]

    x_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Issue X"},
    )
    assert x_resp.status_code == 201
    x_id = x_resp.json()["data"]["id"]

    patch_resp = await client.patch(
        f"/api/v1/issues/{x_id}",
        headers=headers,
        json={"parent_id": x_id},
    )
    assert patch_resp.status_code == 422, patch_resp.text


@pytest.mark.asyncio
async def test_update_issue_rejects_cross_team_parent(client, setup):
    """PATCH parent_id pointing at another team's issue is rejected."""
    headers = setup["headers"]
    team_id = setup["team_id"]

    # A separate team with its own issue. /setup is bootstrap-only
    # (single team), so create the second team via POST /teams authed
    # as the first team's owner — same pattern as test_cross_tenant.
    other_team_resp = await client.post(
        "/api/v1/teams",
        headers=headers,
        json={"name": "Other", "key": "OTHER"},
    )
    assert other_team_resp.status_code == 201, other_team_resp.text
    other_team = other_team_resp.json()["data"]
    other_headers = {
        "X-API-Key": other_team["api_key"],
        "X-User-Id": setup["user_id"],
    }
    other_issue = await client.post(
        f"/api/v1/teams/{other_team['id']}/issues",
        headers=other_headers,
        json={"title": "Other team issue"},
    )
    assert other_issue.status_code == 201, other_issue.text
    other_id = other_issue.json()["data"]["id"]

    # Our own issue
    x_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Issue X"},
    )
    assert x_resp.status_code == 201
    x_id = x_resp.json()["data"]["id"]

    patch_resp = await client.patch(
        f"/api/v1/issues/{x_id}",
        headers=headers,
        json={"parent_id": other_id},
    )
    assert patch_resp.status_code == 422, patch_resp.text


@pytest.mark.asyncio
async def test_completion_rollup_flags_parent(client, setup):
    """When all children complete, parent gets children_all_done flag in triage_context."""
    headers = setup["headers"]
    team_id = setup["team_id"]
    states = setup["states"]

    # Create parent
    parent_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        json={"title": "Fix the faucet"},
        headers=headers,
    )
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["data"]["id"]

    # Create two children
    child_ids = []
    for title in ["Buy washer", "Replace washer"]:
        resp = await client.post(
            f"/api/v1/teams/{team_id}/issues",
            json={"title": title, "parent_id": parent_id, "position": len(child_ids) + 1},
            headers=headers,
        )
        assert resp.status_code == 201
        child_ids.append(resp.json()["data"]["id"])

    # Children default to triage; completion must follow the valid workflow
    # path (triage -> unstarted -> started -> completed) — the state machine
    # rejects a direct triage -> completed jump.
    async def complete(child_id):
        for state_id in (
            states["unstarted"]["id"],
            states["started"]["id"],
            states["completed"]["id"],
        ):
            resp = await client.patch(
                f"/api/v1/issues/{child_id}",
                json={"state_id": state_id},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text

    # Complete first child — parent should NOT be flagged yet
    await complete(child_ids[0])
    parent_resp = await client.get(
        f"/api/v1/issues/{parent_id}",
        headers=headers,
    )
    parent_data = parent_resp.json()["data"]
    assert parent_data.get("triage_context") is None or not parent_data.get(
        "triage_context", {}
    ).get("children_all_done")

    # Complete second child — parent SHOULD be flagged
    await complete(child_ids[1])
    parent_resp = await client.get(
        f"/api/v1/issues/{parent_id}",
        headers=headers,
    )
    parent_data = parent_resp.json()["data"]
    assert parent_data["triage_context"]["children_all_done"] is True
