from datetime import datetime, timedelta

import pytest

from taskstore.scheduler import process_due_recurrences
from taskstore.utils.time import now_utc


@pytest.fixture
async def setup(client):
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": "Home",
            "team_key": "HOME",
            "user_name": "John",
            "user_email": "john@example.com",
            "include_default_labels": False,
        },
    )
    data = resp.json()
    headers = {"X-API-Key": data["api_key"], "X-User-Id": str(data["user_id"])}
    return {"team_id": data["team_id"], "user_id": data["user_id"], "headers": headers}


def _session_factory():
    from tests.conftest import TestSessionLocal

    return TestSessionLocal


@pytest.mark.asyncio
async def test_scheduler_spawns_due_issue(client, setup):
    past = now_utc() - timedelta(hours=1)

    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Change air filters {date}",
            "schedule_type": "interval",
            "schedule_expr": "90d",
            "next_due_at": past.isoformat(),
            "issue_defaults": {"priority": 2, "custom_fields": {"category": "maintenance"}},
        },
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    rec_id = resp.json()["data"]["id"]

    spawned = await process_due_recurrences(_session_factory())
    assert spawned == 1

    # Verify issue was created
    issues_resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/issues",
        headers=setup["headers"],
    )
    issues = issues_resp.json()["data"]
    assert len(issues) == 1
    assert past.strftime("%Y-%m-%d") in issues[0]["title"]
    assert issues[0]["priority"] == 2
    assert issues[0]["custom_fields"]["category"] == "maintenance"

    # Verify recurrence was updated
    rec_resp = await client.get(f"/api/v1/recurrences/{rec_id}", headers=setup["headers"])
    rec = rec_resp.json()["data"]
    assert rec["last_spawned_at"] is not None
    assert rec["last_spawned_issue_id"] == issues[0]["id"]
    next_due = datetime.fromisoformat(rec["next_due_at"])
    assert next_due > now_utc()


@pytest.mark.asyncio
async def test_scheduler_skips_inactive(client, setup):
    past = now_utc() - timedelta(hours=1)

    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Paused task",
            "schedule_type": "interval",
            "schedule_expr": "7d",
            "next_due_at": past.isoformat(),
        },
        headers=setup["headers"],
    )
    rec_id = resp.json()["data"]["id"]

    await client.patch(
        f"/api/v1/recurrences/{rec_id}",
        json={"active": False},
        headers=setup["headers"],
    )

    spawned = await process_due_recurrences(_session_factory())
    assert spawned == 0


@pytest.mark.asyncio
async def test_scheduler_skips_future(client, setup):
    future = now_utc() + timedelta(days=30)

    await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Future task",
            "schedule_type": "interval",
            "schedule_expr": "7d",
            "next_due_at": future.isoformat(),
        },
        headers=setup["headers"],
    )

    spawned = await process_due_recurrences(_session_factory())
    assert spawned == 0


@pytest.mark.asyncio
async def test_scheduler_missed_run_spawns_once(client, setup):
    long_past = now_utc() - timedelta(days=200)

    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Missed task",
            "schedule_type": "interval",
            "schedule_expr": "90d",
            "next_due_at": long_past.isoformat(),
        },
        headers=setup["headers"],
    )
    rec_id = resp.json()["data"]["id"]

    spawned = await process_due_recurrences(_session_factory())
    assert spawned == 1

    issues_resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/issues",
        headers=setup["headers"],
    )
    assert len(issues_resp.json()["data"]) == 1

    rec_resp = await client.get(f"/api/v1/recurrences/{rec_id}", headers=setup["headers"])
    next_due = datetime.fromisoformat(rec_resp.json()["data"]["next_due_at"])
    assert next_due > now_utc()


@pytest.mark.asyncio
async def test_scheduler_spawn_audited(client, setup):
    past = now_utc() - timedelta(hours=1)

    await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Audited spawn",
            "schedule_type": "interval",
            "schedule_expr": "7d",
            "next_due_at": past.isoformat(),
        },
        headers=setup["headers"],
    )

    await process_due_recurrences(_session_factory())

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/audit?entity_type=recurrence_spawn",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 1
    assert entries[0]["entity_type"] == "recurrence_spawn"
