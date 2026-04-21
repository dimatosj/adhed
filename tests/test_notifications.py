import pytest

from tests.conftest import make_team, make_user, get_states_by_type


@pytest.fixture
async def setup(client):
    team = await make_team(client)
    team_id = team["id"]
    api_key = team["api_key"]
    user_id = team["_setup_user_id"]
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
        headers=headers,
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
        headers=headers,
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
        headers=headers,
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
        headers=headers,
        params={"user_id": user_id},
    )
    assert notif_resp.status_code == 200
    notif_id = notif_resp.json()["data"][0]["id"]

    # Mark read
    mark_resp = await client.post(
        f"/api/v1/notifications/{notif_id}/read",
        headers=headers,
    )
    assert mark_resp.status_code == 200
    assert mark_resp.json()["data"]["read"] is True

    # Verify it no longer appears in unread list
    notif_resp2 = await client.get(
        f"/api/v1/teams/{team_id}/notifications",
        headers=headers,
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
        headers=headers,
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
        headers=headers,
    )
    assert len(notif_resp.json()["data"]) == 2

    # Mark all read
    mark_resp = await client.post(
        f"/api/v1/teams/{team_id}/notifications/read-all",
        headers=headers,
    )
    assert mark_resp.status_code == 200

    # Verify all read
    notif_resp2 = await client.get(
        f"/api/v1/teams/{team_id}/notifications",
        headers=headers,
    )
    assert len(notif_resp2.json()["data"]) == 0
