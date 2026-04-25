import pytest


@pytest.fixture
async def setup(client):
    resp = await client.post("/api/v1/setup", json={
        "team_name": "Home", "team_key": "HOME",
        "user_name": "John", "user_email": "john@example.com",
        "include_default_labels": False,
    })
    data = resp.json()
    headers = {"X-API-Key": data["api_key"], "X-User-Id": str(data["user_id"])}
    return {"team_id": data["team_id"], "user_id": data["user_id"], "headers": headers}


async def _make_fragment(client, setup, text="Test note", ftype="memory"):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/fragments",
        json={"text": text, "type": ftype},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_link_between_fragments(client, setup):
    frag_a = await _make_fragment(client, setup, "Person A", "person")
    frag_b = await _make_fragment(client, setup, "Memory B", "memory")

    resp = await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    link = resp.json()["data"]
    assert link["target_type"] == "fragment"
    assert link["target_id"] == frag_b
    assert link["direction"] == "outgoing"
    assert link["summary"] == "Memory B"


@pytest.mark.asyncio
async def test_create_link_to_issue(client, setup):
    frag_id = await _make_fragment(client, setup, "Related to fix", "memory")

    issue_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Fix kitchen faucet", "priority": 2},
        headers=setup["headers"],
    )
    assert issue_resp.status_code == 201
    issue_id = issue_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "issue", "target_id": issue_id},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    link = resp.json()["data"]
    assert link["target_type"] == "issue"
    assert link["summary"] == "Fix kitchen faucet"
    assert "priority" in link["detail"]


@pytest.mark.asyncio
async def test_create_link_to_project(client, setup):
    frag_id = await _make_fragment(client, setup, "Home reno context", "memory")

    proj_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/projects",
        json={"name": "Home renovation"},
        headers=setup["headers"],
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "project", "target_id": proj_id},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    link = resp.json()["data"]
    assert link["target_type"] == "project"
    assert link["summary"] == "Home renovation"
    assert "state" in link["detail"]


@pytest.mark.asyncio
async def test_duplicate_link_returns_409(client, setup):
    frag_a = await _make_fragment(client, setup, "A", "person")
    frag_b = await _make_fragment(client, setup, "B", "memory")

    resp1 = await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_link_to_nonexistent_target_returns_404(client, setup):
    frag_id = await _make_fragment(client, setup, "Orphan linker", "memory")
    fake_id = "00000000-0000-0000-0000-000000000000"

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "fragment", "target_id": fake_id},
        headers=setup["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_target_type_returns_400(client, setup):
    frag_id = await _make_fragment(client, setup, "Bad type", "memory")

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "spaceship", "target_id": "00000000-0000-0000-0000-000000000000"},
        headers=setup["headers"],
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_links_bidirectional(client, setup):
    frag_a = await _make_fragment(client, setup, "Person A", "person")
    frag_b = await _make_fragment(client, setup, "Memory B", "memory")

    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )

    # Outgoing from A
    resp_a = await client.get(f"/api/v1/fragments/{frag_a}/links", headers=setup["headers"])
    assert resp_a.status_code == 200
    links_a = resp_a.json()["data"]
    assert len(links_a) == 1
    assert links_a[0]["direction"] == "outgoing"
    assert links_a[0]["target_id"] == frag_b

    # Incoming to B
    resp_b = await client.get(f"/api/v1/fragments/{frag_b}/links", headers=setup["headers"])
    assert resp_b.status_code == 200
    links_b = resp_b.json()["data"]
    assert len(links_b) == 1
    assert links_b[0]["direction"] == "incoming"
    assert links_b[0]["target_id"] == frag_a


@pytest.mark.asyncio
async def test_get_links_filter_by_target_type(client, setup):
    frag_a = await _make_fragment(client, setup, "Hub", "person")
    frag_b = await _make_fragment(client, setup, "Note", "memory")

    issue_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Some task"},
        headers=setup["headers"],
    )
    issue_id = issue_resp.json()["data"]["id"]

    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "issue", "target_id": issue_id},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/fragments/{frag_a}/links?target_type=issue",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    links = resp.json()["data"]
    assert len(links) == 1
    assert links[0]["target_type"] == "issue"


@pytest.mark.asyncio
async def test_delete_link(client, setup):
    frag_a = await _make_fragment(client, setup, "A", "person")
    frag_b = await _make_fragment(client, setup, "B", "memory")

    create_resp = await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    link_id = create_resp.json()["data"]["id"]

    resp = await client.delete(
        f"/api/v1/fragments/{frag_a}/links/{link_id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 204

    links_resp = await client.get(f"/api/v1/fragments/{frag_a}/links", headers=setup["headers"])
    assert len(links_resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_link_returns_404(client, setup):
    frag_id = await _make_fragment(client, setup, "A", "person")
    fake_link_id = "00000000-0000-0000-0000-000000000000"

    resp = await client.delete(
        f"/api/v1/fragments/{frag_id}/links/{fake_link_id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fragment_link_audited(client, setup):
    frag_a = await _make_fragment(client, setup, "A", "person")
    frag_b = await _make_fragment(client, setup, "B", "memory")

    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/audit?entity_type=fragment_link",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 1
    assert entries[0]["entity_type"] == "fragment_link"
    assert entries[0]["action"] == "create"


@pytest.mark.asyncio
async def test_cascade_delete_removes_links(client, setup):
    frag_a = await _make_fragment(client, setup, "Will be deleted", "person")
    frag_b = await _make_fragment(client, setup, "Stays", "memory")

    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )

    await client.delete(f"/api/v1/fragments/{frag_a}", headers=setup["headers"])

    # Incoming link to B should be gone since source fragment was deleted
    resp = await client.get(f"/api/v1/fragments/{frag_b}/links", headers=setup["headers"])
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0
