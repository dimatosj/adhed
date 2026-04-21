"""Security middleware — CORS, request body size cap.

CORS origins are configured via the CORS_ORIGINS env var (comma-
separated). Request bodies beyond the configurable size limit are
rejected with 413.
"""
import pytest


@pytest.mark.asyncio
async def test_cors_preflight_rejected_by_default(client):
    """With no CORS_ORIGINS configured, preflight from a foreign
    origin gets no Access-Control-Allow-Origin header (the default
    conservative behaviour — CORS is opt-in)."""
    resp = await client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # No CORS header means the browser would block the preflight.
    assert resp.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_request_body_too_large_rejected(client):
    """A request body beyond the configured limit returns 413 before
    any endpoint logic runs."""
    # Default limit is 1 MiB. Send 2 MiB.
    big_body = {"team_name": "X" * (2 * 1024 * 1024), "team_key": "XX",
                "user_name": "a", "user_email": "a@example.com"}
    resp = await client.post("/api/v1/setup", json=big_body)
    assert resp.status_code == 413
