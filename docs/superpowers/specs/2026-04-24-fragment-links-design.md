# Fragment Links — Directed Polymorphic Relationships

*Created: 2026-04-24*

## Summary

First-class directed links between fragments and other entities (fragments, issues, projects). Enables bidirectional traversal: "what's connected to this person?" and "who is linked to this note?" One join table, three API endpoints, hydrated summary responses.

## Data Model

One new table: `fragment_links`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default uuid4 |
| `fragment_id` | UUID | FK → fragments.id, NOT NULL, ON DELETE CASCADE |
| `target_type` | Text | NOT NULL — one of `fragment`, `issue`, `project` |
| `target_id` | UUID | NOT NULL — no FK (polymorphic) |
| `created_by` | UUID | FK → users.id, NOT NULL |
| `created_at` | timestamp | default now_utc |

### Indexes

- `(fragment_id, target_type, target_id)` UNIQUE — prevents duplicate links
- `(target_type, target_id)` — fast reverse lookups

### Integrity

- Deleting a fragment cascades to delete its outgoing links (via FK ON DELETE CASCADE).
- Dangling links (target entity was deleted) are filtered at query time, not prevented by constraints. Polymorphic FKs can't be enforced by Postgres; this is the accepted tradeoff.
- No relation_type column. Links are directed but unlabeled. If labeled edges are needed later, add a nullable `relation_type` text column — no structural change required.

### Bidirectional Traversal

- **Outgoing:** `WHERE fragment_id = :id` — "what does this fragment link to?"
- **Incoming:** `WHERE target_type = 'fragment' AND target_id = :id` — "what links to this fragment?"

Both directions are covered by the two indexes.

## API

### `POST /api/v1/fragments/{fragment_id}/links`

Create a link from a fragment to a target entity.

**Request:**
```json
{"target_type": "fragment", "target_id": "uuid"}
```

**Validation:**
- Source fragment must exist and belong to the authed team
- Target entity must exist (queried by target_type — fragments, issues, or projects table)
- Duplicate links rejected by unique constraint (409)

**Response:** 201 with the created link object.

**Audit:** CREATE entry on entity_type "fragment_link".

### `GET /api/v1/fragments/{fragment_id}/links`

Get all links for a fragment in both directions, with hydrated summaries.

**Query params:**
- `target_type` (optional) — filter to a specific target type

**Response:**
```json
{
  "data": [
    {
      "id": "link-uuid",
      "direction": "outgoing",
      "target_type": "fragment",
      "target_id": "uuid",
      "summary": "Wedding planning checklist",
      "detail": {"fragment_type": "memory"},
      "created_at": "2026-04-24T..."
    },
    {
      "id": "link-uuid",
      "direction": "incoming",
      "target_type": "fragment",
      "target_id": "uuid",
      "summary": "Kristen Taylor",
      "detail": {"fragment_type": "person"},
      "created_at": "2026-04-24T..."
    },
    {
      "id": "link-uuid",
      "direction": "outgoing",
      "target_type": "issue",
      "target_id": "uuid",
      "summary": "Fix kitchen faucet",
      "detail": {"state": "triage", "priority": 2},
      "created_at": "2026-04-24T..."
    },
    {
      "id": "link-uuid",
      "direction": "outgoing",
      "target_type": "project",
      "target_id": "uuid",
      "summary": "Home renovation",
      "detail": {"state": "active"},
      "created_at": "2026-04-24T..."
    }
  ],
  "meta": {"total": 4}
}
```

**Hydration strategy:** Group target IDs by type, execute one query per type (at most 3). No N+1.

**Detail fields by target_type:**
- `fragment` → `{"fragment_type": "person|memory|resource|..."}`
- `issue` → `{"state": "triage|backlog|...", "priority": 2}`
- `project` → `{"state": "planned|active|..."}`

### `DELETE /api/v1/fragments/{fragment_id}/links/{link_id}`

Remove a link. Source fragment must belong to the authed team.

**Response:** 204

**Audit:** DELETE entry on entity_type "fragment_link".

## Service Layer

New file: `services/fragment_link_service.py`

Three functions:

- **`create_link(db, fragment_id, target_type, target_id, user_id)`** — validate source fragment team ownership, validate target exists by querying the appropriate table, insert row, audit, return.
- **`get_links(db, fragment_id, target_type_filter)`** — query outgoing links + incoming links (where target_type='fragment' and target_id=fragment_id). Hydrate by batching target IDs per type into single queries. Merge results with direction labels.
- **`delete_link(db, fragment_id, link_id, user_id)`** — validate link exists and source fragment belongs to authed team, delete, audit.

## Schemas

New file: `schemas/fragment_link.py`

```
FragmentLinkCreate:
  target_type: str  # "fragment" | "issue" | "project"
  target_id: UUID

FragmentLinkResponse:
  id: UUID
  direction: str  # "outgoing" | "incoming"
  target_type: str
  target_id: UUID
  summary: str
  detail: dict
  created_at: datetime
```

## What's NOT in scope

- Auto-linking on entity name match — agents create links explicitly
- Relationship labels/types — links are unlabeled directed edges
- Multi-hop graph traversal — query one fragment's direct links only
- Bulk link creation endpoint
- Modifying existing fragment GET/list responses — links are a separate endpoint
- Link counts on fragment responses

## Migration

Single additive alembic migration:
- CREATE TABLE `fragment_links` with columns, FK constraints, and indexes
- No backfill needed

## Components

### New

| Component | Purpose |
|---|---|
| `models/fragment_link.py` | SQLAlchemy model |
| `schemas/fragment_link.py` | Pydantic schemas |
| `services/fragment_link_service.py` | Business logic |
| `api/fragment_links.py` | Router with 3 endpoints |
| `alembic/versions/..._add_fragment_links.py` | Migration |

### Modified

| Component | Change |
|---|---|
| `main.py` | Register fragment_links router |
