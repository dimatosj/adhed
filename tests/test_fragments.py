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


@pytest.mark.asyncio
async def test_create_fragment(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/fragments",
        json={
            "text": "Tony from Ace Plumbing was great",
            "type": "person",
            "summary": "Tony at Ace Plumbing is a reliable plumber",
            "topics": ["contractors", "home-maintenance"],
            "domains": ["home"],
            "entities": [{"name": "Tony", "type": "person", "role": "plumber", "org": "Ace Plumbing"}],
            "source": {"room": "General"},
        },
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["text"] == "Tony from Ace Plumbing was great"
    assert data["type"] == "person"
    assert data["topics"] == ["contractors", "home-maintenance"]
    assert data["domains"] == ["home"]
    assert len(data["entities"]) == 1
    assert data["entities"][0]["name"] == "Tony"


@pytest.mark.asyncio
async def test_get_fragment(client, setup):
    create = await client.post(
        f"/api/v1/teams/{setup['team_id']}/fragments",
        json={"text": "WiFi: butterfly_orange", "type": "credential", "domains": ["home"]},
        headers=setup["headers"],
    )
    frag_id = create.json()["data"]["id"]

    resp = await client.get(f"/api/v1/fragments/{frag_id}", headers=setup["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["text"] == "WiFi: butterfly_orange"


@pytest.mark.asyncio
async def test_list_fragments_filter_by_type(client, setup):
    headers = setup["headers"]
    tid = setup["team_id"]
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Tony", "type": "person"}, headers=headers)
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "WiFi pass", "type": "credential"}, headers=headers)
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Good day", "type": "journal"}, headers=headers)

    resp = await client.get(f"/api/v1/teams/{tid}/fragments?type=person", headers=headers)
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["type"] == "person"


@pytest.mark.asyncio
async def test_list_fragments_filter_by_domain(client, setup):
    headers = setup["headers"]
    tid = setup["team_id"]
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Dentist note", "type": "person", "domains": ["health"]}, headers=headers)
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Faucet note", "type": "memory", "domains": ["home"]}, headers=headers)

    resp = await client.get(f"/api/v1/teams/{tid}/fragments?domain=health", headers=headers)
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["text"] == "Dentist note"


@pytest.mark.asyncio
async def test_list_fragments_filter_by_topic(client, setup):
    headers = setup["headers"]
    tid = setup["team_id"]
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Great tiles", "type": "resource", "topics": ["kitchen-tiles"]}, headers=headers)
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Nice paint", "type": "resource", "topics": ["paint-colors"]}, headers=headers)

    resp = await client.get(f"/api/v1/teams/{tid}/fragments?topic=kitchen-tiles", headers=headers)
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["text"] == "Great tiles"


@pytest.mark.asyncio
async def test_list_fragments_filter_by_project(client, setup):
    headers = setup["headers"]
    tid = setup["team_id"]
    await client.post(f"/api/v1/teams/{tid}/fragments", json={
        "text": "Tile idea", "type": "idea",
        "source": {"linked_project_id": "proj_abc"},
    }, headers=headers)
    await client.post(f"/api/v1/teams/{tid}/fragments", json={
        "text": "Unlinked note", "type": "memory",
    }, headers=headers)

    resp = await client.get(f"/api/v1/teams/{tid}/fragments?project_id=proj_abc", headers=headers)
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["text"] == "Tile idea"


@pytest.mark.asyncio
async def test_list_fragments_full_text_search(client, setup):
    headers = setup["headers"]
    tid = setup["team_id"]
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Tony from Ace Plumbing", "type": "person"}, headers=headers)
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Great Thai food on 5th", "type": "place"}, headers=headers)

    resp = await client.get(f"/api/v1/teams/{tid}/fragments?title_search=plumbing", headers=headers)
    assert len(resp.json()["data"]) == 1
    assert "Tony" in resp.json()["data"][0]["text"]


@pytest.mark.asyncio
async def test_update_fragment(client, setup):
    headers = setup["headers"]
    create = await client.post(
        f"/api/v1/teams/{setup['team_id']}/fragments",
        json={"text": "Some note", "type": "memory"},
        headers=headers,
    )
    frag_id = create.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/fragments/{frag_id}",
        json={"topics": ["updated-topic"], "source": {"linked_project_id": "proj_xyz"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["topics"] == ["updated-topic"]
    assert resp.json()["data"]["source"]["linked_project_id"] == "proj_xyz"


@pytest.mark.asyncio
async def test_delete_fragment(client, setup):
    headers = setup["headers"]
    create = await client.post(
        f"/api/v1/teams/{setup['team_id']}/fragments",
        json={"text": "Delete me", "type": "memory"},
        headers=headers,
    )
    frag_id = create.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/fragments/{frag_id}", headers=headers)
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/fragments/{frag_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_topics(client, setup):
    headers = setup["headers"]
    tid = setup["team_id"]
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "A", "type": "idea", "topics": ["kitchen-tiles", "home-reno"]}, headers=headers)
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "B", "type": "idea", "topics": ["kitchen-tiles"]}, headers=headers)
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "C", "type": "resource", "topics": ["adhd-tips"]}, headers=headers)

    resp = await client.get(f"/api/v1/teams/{tid}/fragments/topics", headers=headers)
    assert resp.status_code == 200
    topics = resp.json()["data"]
    topic_map = {t["topic"]: t["count"] for t in topics}
    assert topic_map["kitchen-tiles"] == 2
    assert topic_map["home-reno"] == 1
    assert topic_map["adhd-tips"] == 1


@pytest.mark.asyncio
async def test_fragment_audited(client, setup):
    headers = setup["headers"]
    tid = setup["team_id"]
    await client.post(f"/api/v1/teams/{tid}/fragments", json={"text": "Audit me", "type": "memory"}, headers=headers)

    resp = await client.get(f"/api/v1/teams/{tid}/audit?entity_type=fragment", headers=headers)
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 1
    assert entries[0]["entity_type"] == "fragment"
    assert entries[0]["action"] == "create"
