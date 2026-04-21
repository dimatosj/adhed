import pytest


async def make_team(client, name="Acme", key="acme"):
    # Bootstrap via /setup (first team; POST /teams now requires OWNER auth).
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": name,
            "team_key": key,
            "user_name": "Setup",
            "user_email": f"setup-{key}@example.com",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return {
        "id": data["team_id"],
        "name": data["team_name"],
        "key": data["team_key"],
        "api_key": data["api_key"],
        "_setup_user_id": data["user_id"],
    }


async def make_user(client, team_id, api_key, name="Alice", email="alice@example.com"):
    resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers={"X-API-Key": api_key},
        json={"name": name, "email": email},
    )
    assert resp.status_code == 201
    return resp.json()["data"]


async def get_states_by_type(client, team_id, api_key):
    resp = await client.get(
        f"/api/v1/teams/{team_id}/states",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    states = resp.json()["data"]
    by_type = {}
    for s in states:
        by_type[s["type"]] = s
    return by_type


@pytest.fixture
async def setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    user = await make_user(client, team_id, api_key)
    user_id = user["id"]
    headers = {"X-API-Key": api_key, "X-User-Id": user_id}
    states = await get_states_by_type(client, team_id, api_key)
    return {
        "team_id": team_id,
        "api_key": api_key,
        "user_id": user_id,
        "headers": headers,
        "states": states,
    }


@pytest.mark.asyncio
async def test_list_notifications(client, setup):
    s = setup
    headers = s["headers"]
    team_id = s["team_id"]
    api_key = s["api_key"]
    user_id = s["user_id"]

    # Create a rule that sends a notification on issue.created
    rule_resp = await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers={"X-API-Key": api_key},
        json={
            "name": "Notify on create",
            "trigger": "issue.created",
            "conditions": {},
            "actions": [
                {
                    "type": "notify",
                    "message": "Issue created: {title}",
                    "user_id": "$current_user",
                }
            ],
        },
    )
    assert rule_resp.status_code == 201

    # Create an issue to trigger the notification
    issue_resp = await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Test notification issue"},
    )
    assert issue_resp.status_code == 201

    # List notifications
    notif_resp = await client.get(
        f"/api/v1/teams/{team_id}/notifications",
        headers={"X-API-Key": api_key},
        params={"user_id": user_id},
    )
    assert notif_resp.status_code == 200
    data = notif_resp.json()["data"]
    assert len(data) >= 1
    assert "Test notification issue" in data[0]["message"]
    assert data[0]["read"] is False


@pytest.mark.asyncio
async def test_mark_read(client, setup):
    s = setup
    headers = s["headers"]
    team_id = s["team_id"]
    api_key = s["api_key"]
    user_id = s["user_id"]

    # Create rule and issue to generate a notification
    await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers={"X-API-Key": api_key},
        json={
            "name": "Notify on create",
            "trigger": "issue.created",
            "conditions": {},
            "actions": [
                {
                    "type": "notify",
                    "message": "Created: {title}",
                    "user_id": "$current_user",
                }
            ],
        },
    )
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Mark me read"},
    )

    # Get notification
    notif_resp = await client.get(
        f"/api/v1/teams/{team_id}/notifications",
        headers={"X-API-Key": api_key},
        params={"user_id": user_id},
    )
    assert notif_resp.status_code == 200
    notif_id = notif_resp.json()["data"][0]["id"]

    # Mark read
    mark_resp = await client.post(
        f"/api/v1/notifications/{notif_id}/read",
        headers={"X-API-Key": api_key},
    )
    assert mark_resp.status_code == 200
    assert mark_resp.json()["data"]["read"] is True

    # Verify it no longer appears in unread list
    notif_resp2 = await client.get(
        f"/api/v1/teams/{team_id}/notifications",
        headers={"X-API-Key": api_key},
        params={"user_id": user_id},
    )
    assert notif_resp2.status_code == 200
    assert len(notif_resp2.json()["data"]) == 0


@pytest.mark.asyncio
async def test_mark_all_read(client, setup):
    s = setup
    headers = s["headers"]
    team_id = s["team_id"]
    api_key = s["api_key"]
    user_id = s["user_id"]

    # Create rule and two issues to generate two notifications
    await client.post(
        f"/api/v1/teams/{team_id}/rules",
        headers={"X-API-Key": api_key},
        json={
            "name": "Notify on create",
            "trigger": "issue.created",
            "conditions": {},
            "actions": [
                {
                    "type": "notify",
                    "message": "Created: {title}",
                    "user_id": "$current_user",
                }
            ],
        },
    )
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Issue A"},
    )
    await client.post(
        f"/api/v1/teams/{team_id}/issues",
        headers=headers,
        json={"title": "Issue B"},
    )

    # Verify we have 2 notifications
    notif_resp = await client.get(
        f"/api/v1/teams/{team_id}/notifications",
        headers={"X-API-Key": api_key},
    )
    assert len(notif_resp.json()["data"]) == 2

    # Mark all read
    mark_resp = await client.post(
        f"/api/v1/teams/{team_id}/notifications/read-all",
        headers={"X-API-Key": api_key},
    )
    assert mark_resp.status_code == 200

    # Verify all read
    notif_resp2 = await client.get(
        f"/api/v1/teams/{team_id}/notifications",
        headers={"X-API-Key": api_key},
    )
    assert len(notif_resp2.json()["data"]) == 0
