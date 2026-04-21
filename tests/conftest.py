import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import taskstore.models  # noqa: F401 — ensure all models are registered
from taskstore.api.deps import get_db
from taskstore.database import Base
from taskstore.main import app

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    # Default matches docker-compose.yml credentials (adhed/adhed) so
    # `docker compose up -d adhed-db` + `pytest` works out of the box.
    # Override with TEST_DATABASE_URL if you run Postgres elsewhere.
    "postgresql+asyncpg://adhed:adhed@localhost:5433/adhed_test",
)

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def truncate_tables():
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def make_team(client, name="Acme", key="ACME"):
    resp = await client.post(
        "/api/v1/setup",
        json={
            "team_name": name,
            "team_key": key,
            "user_name": "Setup",
            "user_email": f"setup-{key.lower()}@example.com",
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


async def make_user(
    client,
    team_id,
    api_key,
    name="Alice",
    email="alice@example.com",
    as_user_id=None,
):
    # POST /teams/{id}/users requires ADMIN+ since PR 2 — callers must
    # auth as an existing admin/owner. Most tests call this right after
    # make_team(), so pass make_team(...)["_setup_user_id"] here.
    headers = {"X-API-Key": api_key}
    if as_user_id is not None:
        headers["X-User-Id"] = as_user_id
    resp = await client.post(
        f"/api/v1/teams/{team_id}/users",
        headers=headers,
        json={"name": name, "email": email},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def get_states_by_type(client, team_id, api_key):
    resp = await client.get(
        f"/api/v1/teams/{team_id}/states",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    return {s["type"]: s for s in resp.json()["data"]}
