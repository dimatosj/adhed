import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from taskstore.services.recurrence_service import (
    parse_interval,
    compute_next_due,
    render_title,
    validate_schedule,
)
from taskstore.models.enums import ScheduleType


# --- Unit tests for schedule parsing ---

def test_parse_interval_days():
    delta = parse_interval("90d")
    assert delta == timedelta(days=90)


def test_parse_interval_weeks():
    delta = parse_interval("2w")
    assert delta == timedelta(weeks=2)


def test_parse_interval_months():
    delta = parse_interval("3m")
    base = datetime(2026, 1, 15, tzinfo=timezone.utc)
    result = base + delta
    assert result == datetime(2026, 4, 15, tzinfo=timezone.utc)


def test_parse_interval_invalid():
    with pytest.raises(ValueError):
        parse_interval("abc")


def test_parse_interval_invalid_unit():
    with pytest.raises(ValueError):
        parse_interval("5x")


def test_compute_next_due_interval():
    after = datetime(2026, 5, 1, 9, 0)
    result = compute_next_due(ScheduleType.INTERVAL, "7d", after)
    assert result == datetime(2026, 5, 8, 9, 0)


def test_compute_next_due_cron():
    after = datetime(2026, 5, 1, 8, 0)
    result = compute_next_due(ScheduleType.CRON, "0 9 * * *", after)
    assert result == datetime(2026, 5, 1, 9, 0)


def test_compute_next_due_cron_past():
    after = datetime(2026, 5, 1, 10, 0)
    result = compute_next_due(ScheduleType.CRON, "0 9 * * *", after)
    assert result == datetime(2026, 5, 2, 9, 0)


def test_render_title_with_date():
    dt = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
    assert render_title("Change air filters {date}", dt) == "Change air filters 2026-07-01"


def test_render_title_no_placeholder():
    dt = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
    assert render_title("Weekly review", dt) == "Weekly review"


def test_validate_schedule_valid_cron():
    validate_schedule(ScheduleType.CRON, "0 9 * * MON")


def test_validate_schedule_invalid_cron():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        validate_schedule(ScheduleType.CRON, "not a cron")
    assert exc_info.value.status_code == 422


def test_validate_schedule_valid_interval():
    validate_schedule(ScheduleType.INTERVAL, "90d")


def test_validate_schedule_invalid_interval():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        validate_schedule(ScheduleType.INTERVAL, "abc")
    assert exc_info.value.status_code == 422


# --- Integration tests for CRUD ---

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
async def test_create_interval_recurrence(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Change air filters",
            "schedule_type": "interval",
            "schedule_expr": "90d",
            "issue_defaults": {"priority": 2, "custom_fields": {"readiness": "ready"}},
        },
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    rec = resp.json()["data"]
    assert rec["title_template"] == "Change air filters"
    assert rec["schedule_type"] == "interval"
    assert rec["schedule_expr"] == "90d"
    assert rec["active"] is True
    assert rec["last_spawned_at"] is None


@pytest.mark.asyncio
async def test_create_cron_recurrence(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Weekly review {date}",
            "schedule_type": "cron",
            "schedule_expr": "0 9 * * MON",
        },
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["schedule_type"] == "cron"


@pytest.mark.asyncio
async def test_create_with_explicit_next_due(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Quarterly filter change",
            "schedule_type": "interval",
            "schedule_expr": "90d",
            "next_due_at": "2026-07-01T09:00:00Z",
        },
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    assert "2026-07-01" in resp.json()["data"]["next_due_at"]


@pytest.mark.asyncio
async def test_invalid_cron_returns_422(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Bad cron",
            "schedule_type": "cron",
            "schedule_expr": "not valid",
        },
        headers=setup["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_interval_returns_422(client, setup):
    resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={
            "title_template": "Bad interval",
            "schedule_type": "interval",
            "schedule_expr": "abc",
        },
        headers=setup["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_recurrences(client, setup):
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "A", "schedule_type": "interval", "schedule_expr": "7d"},
        headers=setup["headers"],
    )
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "B", "schedule_type": "cron", "schedule_expr": "0 9 * * MON"},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_list_filter_by_active(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "Active", "schedule_type": "interval", "schedule_expr": "7d"},
        headers=setup["headers"],
    )
    rec_id = create_resp.json()["data"]["id"]

    await client.patch(
        f"/api/v1/recurrences/{rec_id}",
        json={"active": False},
        headers=setup["headers"],
    )

    await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "Still active", "schedule_type": "interval", "schedule_expr": "7d"},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/recurrences?active=true",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_get_recurrence(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "Filter change", "schedule_type": "interval", "schedule_expr": "90d"},
        headers=setup["headers"],
    )
    rec_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/v1/recurrences/{rec_id}", headers=setup["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == rec_id


@pytest.mark.asyncio
async def test_get_nonexistent_returns_404(client, setup):
    resp = await client.get(
        "/api/v1/recurrences/00000000-0000-0000-0000-000000000000",
        headers=setup["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_recurrence(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "Old title", "schedule_type": "interval", "schedule_expr": "30d"},
        headers=setup["headers"],
    )
    rec_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/recurrences/{rec_id}",
        json={"title_template": "New title", "schedule_expr": "60d"},
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title_template"] == "New title"
    assert resp.json()["data"]["schedule_expr"] == "60d"


@pytest.mark.asyncio
async def test_pause_resume(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "Pausable", "schedule_type": "interval", "schedule_expr": "7d"},
        headers=setup["headers"],
    )
    rec_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/recurrences/{rec_id}",
        json={"active": False},
        headers=setup["headers"],
    )
    assert resp.json()["data"]["active"] is False

    resp = await client.patch(
        f"/api/v1/recurrences/{rec_id}",
        json={"active": True},
        headers=setup["headers"],
    )
    assert resp.json()["data"]["active"] is True


@pytest.mark.asyncio
async def test_delete_recurrence(client, setup):
    create_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "Deletable", "schedule_type": "interval", "schedule_expr": "7d"},
        headers=setup["headers"],
    )
    rec_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/recurrences/{rec_id}", headers=setup["headers"])
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/recurrences/{rec_id}", headers=setup["headers"])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recurrence_audited(client, setup):
    await client.post(
        f"/api/v1/teams/{setup['team_id']}/recurrences",
        json={"title_template": "Audited", "schedule_type": "interval", "schedule_expr": "7d"},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/audit?entity_type=recurrence",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 1
    assert entries[0]["entity_type"] == "recurrence"
    assert entries[0]["action"] == "create"
