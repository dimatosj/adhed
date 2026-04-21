"""M8: custom_fields size cap.

JSONB columns accept arbitrarily nested data. Without a cap, a
client could POST a 500 KiB nested object per issue, inflating
DB storage and slowing the GIN index. Enforced at the schema
layer so the cap is visible in the OpenAPI spec too.
"""

import pytest

from tests.conftest import make_team


async def _bootstrap(client):
    team = await make_team(client)
    return team, {
        "X-API-Key": team["api_key"],
        "X-User-Id": team["_setup_user_id"],
    }


@pytest.mark.asyncio
async def test_reasonable_custom_fields_accepted(client):
    team, headers = await _bootstrap(client)
    resp = await client.post(
        f"/api/v1/teams/{team['id']}/issues",
        headers=headers,
        json={
            "title": "has custom fields",
            "custom_fields": {
                "jira_id": "PROJ-123",
                "severity": "p2",
                "tags": ["ops", "backend"],
            },
        },
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_oversized_custom_fields_rejected(client):
    team, headers = await _bootstrap(client)
    # Serialized size > cap (16 KiB default)
    huge = {"bloat": "x" * 20_000}
    resp = await client.post(
        f"/api/v1/teams/{team['id']}/issues",
        headers=headers,
        json={"title": "bloaty", "custom_fields": huge},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["data"] is None
    assert any("custom_fields" in e["message"].lower() for e in body["errors"])
