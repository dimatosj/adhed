import pytest

SETUP_PAYLOAD = {
    "team_name": "My Team",
    "team_key": "myteam",
    "user_name": "Alice",
    "user_email": "alice@example.com",
}


@pytest.mark.asyncio
async def test_setup_creates_team_user_labels(client):
    resp = await client.post("/api/v1/setup", json=SETUP_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["team_name"] == "My Team"
    assert data["team_key"] == "MYTEAM"
    assert data["api_key"].startswith("adhed_")
    assert data["user_name"] == "Alice"
    assert data["user_email"] == "alice@example.com"
    assert "team_id" in data
    assert "user_id" in data


@pytest.mark.asyncio
async def test_setup_seeds_default_states(client):
    resp = await client.post("/api/v1/setup", json=SETUP_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    team_id = data["team_id"]
    api_key = data["api_key"]

    states_resp = await client.get(
        f"/api/v1/teams/{team_id}/states",
        headers={"X-API-Key": api_key},
    )
    assert states_resp.status_code == 200
    states = states_resp.json()["data"]
    assert len(states) == 6


@pytest.mark.asyncio
async def test_setup_seeds_default_labels(client):
    resp = await client.post("/api/v1/setup", json=SETUP_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    team_id = data["team_id"]
    api_key = data["api_key"]

    labels_resp = await client.get(
        f"/api/v1/teams/{team_id}/labels",
        headers={"X-API-Key": api_key},
    )
    assert labels_resp.status_code == 200
    labels = labels_resp.json()["data"]
    assert len(labels) == 14

    label_names = {lb["name"] for lb in labels}
    expected = {
        "health", "home", "personal", "family", "work", "finances", "social",
        "@home", "@errands", "@computer", "@phone", "someday-maybe", "waiting-for",
        "commitment",
    }
    assert label_names == expected


@pytest.mark.asyncio
async def test_setup_returns_409_on_second_call(client):
    resp1 = await client.post("/api/v1/setup", json=SETUP_PAYLOAD)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/setup", json=SETUP_PAYLOAD)
    assert resp2.status_code == 409
    assert resp2.json()["detail"] == "Already set up"
