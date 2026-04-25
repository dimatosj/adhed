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
