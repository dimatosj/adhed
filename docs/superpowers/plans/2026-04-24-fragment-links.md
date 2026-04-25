# Fragment Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add directed polymorphic links between fragments and other entities (fragments, issues, projects) with bidirectional traversal and hydrated summaries.

**Architecture:** One new `fragment_links` join table with polymorphic `target_type`/`target_id`. Three API endpoints (create, list, delete) nested under `/api/v1/fragments/{fragment_id}/links`. Service layer handles validation, hydration (batch queries grouped by target_type), and audit. No FK on target — dangling links filtered at query time.

**Tech Stack:** SQLAlchemy async, FastAPI, Pydantic, Alembic, PostgreSQL

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/taskstore/models/fragment_link.py` | SQLAlchemy ORM model |
| Create | `src/taskstore/schemas/fragment_link.py` | Pydantic request/response schemas |
| Create | `src/taskstore/services/fragment_link_service.py` | Validation, hydration, CRUD |
| Create | `src/taskstore/api/fragment_links.py` | Router with 3 endpoints |
| Create | `alembic/versions/g4b2_add_fragment_links.py` | Migration |
| Create | `tests/test_fragment_links.py` | Full endpoint test coverage |
| Modify | `src/taskstore/models/__init__.py` | Register FragmentLink model |
| Modify | `src/taskstore/main.py` | Register fragment_links router |

---

### Task 1: Model

**Files:**
- Create: `src/taskstore/models/fragment_link.py`
- Modify: `src/taskstore/models/__init__.py`

- [ ] **Step 1: Create the FragmentLink model**

```python
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from taskstore.database import Base
from taskstore.utils.time import now_utc


class FragmentLink(Base):
    __tablename__ = "fragment_links"
    __table_args__ = (
        UniqueConstraint("fragment_id", "target_type", "target_id", name="uq_fragment_link"),
        Index("ix_fragment_links_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fragment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fragments.id", ondelete="CASCADE"), nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
```

- [ ] **Step 2: Register the model in `models/__init__.py`**

Add this import to `src/taskstore/models/__init__.py`:

```python
from taskstore.models.fragment_link import FragmentLink  # noqa: F401
```

Add it after the `Fragment` import line.

- [ ] **Step 3: Verify model loads**

Run: `cd /Users/jsd/projects/adhed && source .venv/bin/activate && python -c "from taskstore.models.fragment_link import FragmentLink; print(FragmentLink.__tablename__)"`

Expected: `fragment_links`

- [ ] **Step 4: Commit**

```bash
git add src/taskstore/models/fragment_link.py src/taskstore/models/__init__.py
git commit -m "feat: add FragmentLink model"
```

---

### Task 2: Schemas

**Files:**
- Create: `src/taskstore/schemas/fragment_link.py`

- [ ] **Step 1: Create the schemas file**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class FragmentLinkCreate(BaseModel):
    target_type: str
    target_id: uuid.UUID


class FragmentLinkResponse(BaseModel):
    id: uuid.UUID
    direction: str
    target_type: str
    target_id: uuid.UUID
    summary: str
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Verify schemas load**

Run: `cd /Users/jsd/projects/adhed && source .venv/bin/activate && python -c "from taskstore.schemas.fragment_link import FragmentLinkCreate, FragmentLinkResponse; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/taskstore/schemas/fragment_link.py
git commit -m "feat: add fragment link schemas"
```

---

### Task 3: Service Layer

**Files:**
- Create: `src/taskstore/services/fragment_link_service.py`

- [ ] **Step 1: Write the failing test for create_link**

Create `tests/test_fragment_links.py`:

```python
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
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd /Users/jsd/projects/adhed && source .venv/bin/activate && pytest tests/test_fragment_links.py::test_create_link_between_fragments -v`

Expected: FAIL (404 — route doesn't exist yet)

- [ ] **Step 3: Create the service file**

Create `src/taskstore/services/fragment_link_service.py`:

```python
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import record_audit
from taskstore.models.enums import AuditAction
from taskstore.models.fragment import Fragment
from taskstore.models.fragment_link import FragmentLink
from taskstore.models.issue import Issue
from taskstore.models.project import Project
from taskstore.schemas.fragment_link import FragmentLinkResponse

VALID_TARGET_TYPES = frozenset({"fragment", "issue", "project"})

TARGET_TABLE = {
    "fragment": Fragment,
    "issue": Issue,
    "project": Project,
}


async def _validate_source(db: AsyncSession, fragment_id: uuid.UUID, team_id: uuid.UUID) -> Fragment:
    result = await db.execute(select(Fragment).where(Fragment.id == fragment_id))
    frag = result.scalar_one_or_none()
    if not frag:
        raise HTTPException(status_code=404, detail="Source fragment not found")
    if frag.team_id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return frag


async def _validate_target(db: AsyncSession, target_type: str, target_id: uuid.UUID) -> None:
    if target_type not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid target_type: {target_type}")
    model = TARGET_TABLE[target_type]
    result = await db.execute(select(model).where(model.id == target_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Target {target_type} not found")


def _hydrate_fragment(frag: Fragment) -> tuple[str, dict]:
    return (frag.summary or frag.text[:80]), {"fragment_type": frag.type.value if frag.type else None}


def _hydrate_issue(issue: Issue) -> tuple[str, dict]:
    return issue.title, {"state_id": str(issue.state_id), "priority": issue.priority}


def _hydrate_project(project: Project) -> tuple[str, dict]:
    return project.name, {"state": project.state.value if project.state else None}


HYDRATORS = {
    "fragment": (Fragment, _hydrate_fragment),
    "issue": (Issue, _hydrate_issue),
    "project": (Project, _hydrate_project),
}


async def _hydrate_links(
    db: AsyncSession,
    links: list[FragmentLink],
    directions: dict[uuid.UUID, str],
) -> list[FragmentLinkResponse]:
    grouped: dict[str, list[FragmentLink]] = {}
    for link in links:
        grouped.setdefault(link.target_type, []).append(link)

    hydrated: dict[uuid.UUID, tuple[str, dict]] = {}
    for target_type, type_links in grouped.items():
        model, hydrator = HYDRATORS[target_type]
        ids = [link.target_id for link in type_links]
        result = await db.execute(select(model).where(model.id.in_(ids)))
        entities = {e.id: e for e in result.scalars().all()}
        for link in type_links:
            entity = entities.get(link.target_id)
            if entity:
                hydrated[link.id] = hydrator(entity)

    responses = []
    for link in links:
        summary, detail = hydrated.get(link.id, ("(deleted)", {}))
        responses.append(FragmentLinkResponse(
            id=link.id,
            direction=directions[link.id],
            target_type=link.target_type,
            target_id=link.target_id,
            summary=summary,
            detail=detail,
            created_at=link.created_at,
        ))
    return responses


async def create_link(
    db: AsyncSession,
    fragment_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    user_id: uuid.UUID,
    team_id: uuid.UUID,
) -> FragmentLinkResponse:
    source = await _validate_source(db, fragment_id, team_id)
    await _validate_target(db, target_type, target_id)

    link = FragmentLink(
        fragment_id=fragment_id,
        target_type=target_type,
        target_id=target_id,
        created_by=user_id,
    )
    db.add(link)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Link already exists")

    await record_audit(db, source.team_id, "fragment_link", link.id, AuditAction.CREATE, user_id)
    await db.commit()
    await db.refresh(link)

    responses = await _hydrate_links(db, [link], {link.id: "outgoing"})
    return responses[0]


async def get_links(
    db: AsyncSession,
    fragment_id: uuid.UUID,
    team_id: uuid.UUID,
    target_type_filter: str | None = None,
) -> list[FragmentLinkResponse]:
    await _validate_source(db, fragment_id, team_id)

    outgoing_q = select(FragmentLink).where(FragmentLink.fragment_id == fragment_id)
    if target_type_filter:
        outgoing_q = outgoing_q.where(FragmentLink.target_type == target_type_filter)
    outgoing_result = await db.execute(outgoing_q)
    outgoing = list(outgoing_result.scalars().all())

    incoming_q = (
        select(FragmentLink)
        .where(FragmentLink.target_type == "fragment")
        .where(FragmentLink.target_id == fragment_id)
    )
    if target_type_filter and target_type_filter != "fragment":
        incoming = []
    else:
        incoming_result = await db.execute(incoming_q)
        incoming = list(incoming_result.scalars().all())

    directions: dict[uuid.UUID, str] = {}
    for link in outgoing:
        directions[link.id] = "outgoing"

    incoming_remapped = []
    for link in incoming:
        directions[link.id] = "incoming"
        incoming_remapped.append(link)

    all_links = outgoing + incoming_remapped

    for link in incoming_remapped:
        link.target_id = link.fragment_id
        link.target_type = "fragment"

    return await _hydrate_links(db, all_links, directions)


async def delete_link(
    db: AsyncSession,
    fragment_id: uuid.UUID,
    link_id: uuid.UUID,
    user_id: uuid.UUID,
    team_id: uuid.UUID,
) -> None:
    source = await _validate_source(db, fragment_id, team_id)
    result = await db.execute(
        select(FragmentLink).where(FragmentLink.id == link_id, FragmentLink.fragment_id == fragment_id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    await record_audit(db, source.team_id, "fragment_link", link.id, AuditAction.DELETE, user_id)
    await db.delete(link)
    await db.commit()
```

- [ ] **Step 4: Commit**

```bash
git add src/taskstore/services/fragment_link_service.py tests/test_fragment_links.py
git commit -m "feat: add fragment link service layer and initial test"
```

---

### Task 4: API Router

**Files:**
- Create: `src/taskstore/api/fragment_links.py`
- Modify: `src/taskstore/main.py`

- [ ] **Step 1: Create the router**

Create `src/taskstore/api/fragment_links.py`:

```python
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_current_user, get_db
from taskstore.api.deps import get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.fragment_link import FragmentLinkCreate, FragmentLinkResponse
from taskstore.services import fragment_link_service

router = APIRouter(tags=["fragment-links"])


@router.post(
    "/api/v1/fragments/{fragment_id}/links",
    response_model=Envelope[FragmentLinkResponse],
    status_code=201,
)
async def create_link(
    fragment_id: uuid.UUID,
    data: FragmentLinkCreate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link = await fragment_link_service.create_link(
        db, fragment_id, data.target_type, data.target_id, user.id, authed_team.id,
    )
    return Envelope(data=link)


@router.get(
    "/api/v1/fragments/{fragment_id}/links",
    response_model=Envelope[list[FragmentLinkResponse]],
)
async def get_links(
    fragment_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
    target_type: str | None = Query(None),
):
    links = await fragment_link_service.get_links(
        db, fragment_id, authed_team.id, target_type_filter=target_type,
    )
    return Envelope(data=links, meta=Meta(total=len(links)))


@router.delete(
    "/api/v1/fragments/{fragment_id}/links/{link_id}",
    status_code=204,
)
async def delete_link(
    fragment_id: uuid.UUID,
    link_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await fragment_link_service.delete_link(db, fragment_id, link_id, user.id, authed_team.id)
```

- [ ] **Step 2: Register the router in `main.py`**

Add the import after the `fragments_router` import:

```python
from taskstore.api.fragment_links import router as fragment_links_router
```

Add the router registration after `fragments_router`:

```python
app.include_router(fragment_links_router)
```

- [ ] **Step 3: Run the create link test**

Run: `cd /Users/jsd/projects/adhed && source .venv/bin/activate && pytest tests/test_fragment_links.py::test_create_link_between_fragments -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/taskstore/api/fragment_links.py src/taskstore/main.py
git commit -m "feat: add fragment links API router and wire into app"
```

---

### Task 5: Full Test Coverage

**Files:**
- Modify: `tests/test_fragment_links.py`

- [ ] **Step 1: Add remaining tests**

Append the following tests to `tests/test_fragment_links.py`:

```python
@pytest.mark.asyncio
async def test_create_link_to_issue(client, setup):
    frag_id = await _make_fragment(client, setup, "Related to fix", "memory")

    issue_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Fix kitchen faucet", "priority": 2},
        headers=setup["headers"],
    )
    assert issue_resp.status_code == 201
    issue_id = issue_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "issue", "target_id": issue_id},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    link = resp.json()["data"]
    assert link["target_type"] == "issue"
    assert link["summary"] == "Fix kitchen faucet"
    assert "priority" in link["detail"]


@pytest.mark.asyncio
async def test_create_link_to_project(client, setup):
    frag_id = await _make_fragment(client, setup, "Home reno context", "memory")

    proj_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/projects",
        json={"name": "Home renovation"},
        headers=setup["headers"],
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "project", "target_id": proj_id},
        headers=setup["headers"],
    )
    assert resp.status_code == 201
    link = resp.json()["data"]
    assert link["target_type"] == "project"
    assert link["summary"] == "Home renovation"
    assert "state" in link["detail"]


@pytest.mark.asyncio
async def test_duplicate_link_returns_409(client, setup):
    frag_a = await _make_fragment(client, setup, "A", "person")
    frag_b = await _make_fragment(client, setup, "B", "memory")

    resp1 = await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_link_to_nonexistent_target_returns_404(client, setup):
    frag_id = await _make_fragment(client, setup, "Orphan linker", "memory")
    fake_id = "00000000-0000-0000-0000-000000000000"

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "fragment", "target_id": fake_id},
        headers=setup["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_target_type_returns_400(client, setup):
    frag_id = await _make_fragment(client, setup, "Bad type", "memory")

    resp = await client.post(
        f"/api/v1/fragments/{frag_id}/links",
        json={"target_type": "spaceship", "target_id": "00000000-0000-0000-0000-000000000000"},
        headers=setup["headers"],
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_links_bidirectional(client, setup):
    frag_a = await _make_fragment(client, setup, "Person A", "person")
    frag_b = await _make_fragment(client, setup, "Memory B", "memory")

    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )

    # Outgoing from A
    resp_a = await client.get(f"/api/v1/fragments/{frag_a}/links", headers=setup["headers"])
    assert resp_a.status_code == 200
    links_a = resp_a.json()["data"]
    assert len(links_a) == 1
    assert links_a[0]["direction"] == "outgoing"
    assert links_a[0]["target_id"] == frag_b

    # Incoming to B
    resp_b = await client.get(f"/api/v1/fragments/{frag_b}/links", headers=setup["headers"])
    assert resp_b.status_code == 200
    links_b = resp_b.json()["data"]
    assert len(links_b) == 1
    assert links_b[0]["direction"] == "incoming"
    assert links_b[0]["target_id"] == frag_a


@pytest.mark.asyncio
async def test_get_links_filter_by_target_type(client, setup):
    frag_a = await _make_fragment(client, setup, "Hub", "person")
    frag_b = await _make_fragment(client, setup, "Note", "memory")

    issue_resp = await client.post(
        f"/api/v1/teams/{setup['team_id']}/issues",
        json={"title": "Some task"},
        headers=setup["headers"],
    )
    issue_id = issue_resp.json()["data"]["id"]

    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "issue", "target_id": issue_id},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/fragments/{frag_a}/links?target_type=issue",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    links = resp.json()["data"]
    assert len(links) == 1
    assert links[0]["target_type"] == "issue"


@pytest.mark.asyncio
async def test_delete_link(client, setup):
    frag_a = await _make_fragment(client, setup, "A", "person")
    frag_b = await _make_fragment(client, setup, "B", "memory")

    create_resp = await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )
    link_id = create_resp.json()["data"]["id"]

    resp = await client.delete(
        f"/api/v1/fragments/{frag_a}/links/{link_id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 204

    links_resp = await client.get(f"/api/v1/fragments/{frag_a}/links", headers=setup["headers"])
    assert len(links_resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_link_returns_404(client, setup):
    frag_id = await _make_fragment(client, setup, "A", "person")
    fake_link_id = "00000000-0000-0000-0000-000000000000"

    resp = await client.delete(
        f"/api/v1/fragments/{frag_id}/links/{fake_link_id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fragment_link_audited(client, setup):
    frag_a = await _make_fragment(client, setup, "A", "person")
    frag_b = await _make_fragment(client, setup, "B", "memory")

    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/teams/{setup['team_id']}/audit?entity_type=fragment_link",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 1
    assert entries[0]["entity_type"] == "fragment_link"
    assert entries[0]["action"] == "create"


@pytest.mark.asyncio
async def test_cascade_delete_removes_links(client, setup):
    frag_a = await _make_fragment(client, setup, "Will be deleted", "person")
    frag_b = await _make_fragment(client, setup, "Stays", "memory")

    await client.post(
        f"/api/v1/fragments/{frag_a}/links",
        json={"target_type": "fragment", "target_id": frag_b},
        headers=setup["headers"],
    )

    await client.delete(f"/api/v1/fragments/{frag_a}", headers=setup["headers"])

    # Incoming link to B should be gone since source fragment was deleted
    resp = await client.get(f"/api/v1/fragments/{frag_b}/links", headers=setup["headers"])
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0
```

- [ ] **Step 2: Run the full test file**

Run: `cd /Users/jsd/projects/adhed && source .venv/bin/activate && pytest tests/test_fragment_links.py -v`

Expected: All tests PASS

- [ ] **Step 3: Run the entire test suite to check for regressions**

Run: `cd /Users/jsd/projects/adhed && source .venv/bin/activate && pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_fragment_links.py
git commit -m "test: full coverage for fragment links endpoints"
```

---

### Task 6: Migration

**Files:**
- Create: `alembic/versions/g4b2_add_fragment_links.py`

- [ ] **Step 1: Create the migration**

Create `alembic/versions/g4b2_add_fragment_links.py`:

```python
"""add fragment_links table

Revision ID: g4b2
Revises: f3a1
Create Date: 2026-04-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'g4b2'
down_revision: Union[str, Sequence[str], None] = 'f3a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fragment_links',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('fragment_id', UUID(as_uuid=True), sa.ForeignKey('fragments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('target_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('fragment_id', 'target_type', 'target_id', name='uq_fragment_link'),
    )
    op.create_index('ix_fragment_links_target', 'fragment_links', ['target_type', 'target_id'])


def downgrade() -> None:
    op.drop_index('ix_fragment_links_target', table_name='fragment_links')
    op.drop_table('fragment_links')
```

- [ ] **Step 2: Run the migration against the dev database**

Run: `cd /Users/jsd/projects/adhed && source .venv/bin/activate && alembic upgrade head`

Expected: Output showing migration `g4b2` applied successfully.

- [ ] **Step 3: Verify the table exists**

Run: `docker exec -i adhed-adhed-db-1 psql -U adhed -d adhed -c "\d fragment_links"`

Expected: Table structure with all columns, constraints, and indexes.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/g4b2_add_fragment_links.py
git commit -m "feat: add fragment_links migration"
```

---

### Task 7: Integration Verification

- [ ] **Step 1: Rebuild the Docker container**

Run: `cd /Users/jsd/projects/adhed && docker compose up -d --build`

Expected: Container rebuilds and starts.

- [ ] **Step 2: Run the migration inside Docker**

Run: `docker exec -i adhed-adhed-api-1 alembic upgrade head`

Expected: Migration applied (or already at head).

- [ ] **Step 3: Smoke test — create a link via curl**

```bash
source /Users/jsd/projects/adhed/.adhed-credentials

# Create two fragments
FRAG_A=$(curl -sf -X POST "$URL/api/v1/teams/$TEAM_ID/fragments" \
  -H "X-API-Key: $API_KEY" -H "X-User-Id: $USER_ID" -H "Content-Type: application/json" \
  -d '{"text":"Smoke test person","type":"person"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

FRAG_B=$(curl -sf -X POST "$URL/api/v1/teams/$TEAM_ID/fragments" \
  -H "X-API-Key: $API_KEY" -H "X-User-Id: $USER_ID" -H "Content-Type: application/json" \
  -d '{"text":"Smoke test memory","type":"memory","summary":"A childhood memory"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# Create a link
curl -sf -X POST "$URL/api/v1/fragments/$FRAG_A/links" \
  -H "X-API-Key: $API_KEY" -H "X-User-Id: $USER_ID" -H "Content-Type: application/json" \
  -d "{\"target_type\":\"fragment\",\"target_id\":\"$FRAG_B\"}" | python3 -m json.tool

# Get links (from A — should show outgoing)
curl -sf "$URL/api/v1/fragments/$FRAG_A/links" \
  -H "X-API-Key: $API_KEY" -H "X-User-Id: $USER_ID" | python3 -m json.tool

# Get links (from B — should show incoming)
curl -sf "$URL/api/v1/fragments/$FRAG_B/links" \
  -H "X-API-Key: $API_KEY" -H "X-User-Id: $USER_ID" | python3 -m json.tool
```

Expected: Link created with 201, outgoing link visible from A, incoming link visible from B with hydrated summaries.

- [ ] **Step 4: Run the full test suite one final time**

Run: `cd /Users/jsd/projects/adhed && source .venv/bin/activate && pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 5: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "feat: fragment links — complete implementation"
```
