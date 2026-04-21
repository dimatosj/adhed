# Architecture

ADHED is a three-layer application: **engine**, **rules**, and
**API**. Each layer has a narrow responsibility and depends only
downward.

```
┌─────────────────────────────────────────────────────────────┐
│                            API                             │
│  FastAPI routers  •  dependency-injected auth + role gates  │
│  Uniform error envelope  •  Pydantic schemas                │
└──────────────────────────┬──────────────────────────────────┘
                           │ calls
┌──────────────────────────▼──────────────────────────────────┐
│                        Services                             │
│   Business logic: CRUD with side-effects, audit, validation │
└────────┬────────────────────────────┬────────────────────────┘
         │ calls                      │ calls
┌────────▼─────────┐         ┌────────▼────────┐
│   Rules Engine   │         │   Core Engine   │
│  evaluate →      │         │  transitions    │
│  apply effects   │         │  audit          │
│  (conditions,    │         │  defaults       │
│   actions)       │         │                 │
└────────┬─────────┘         └────────┬────────┘
         │                            │
         └────────────┬───────────────┘
                      │
              ┌───────▼────────┐
              │     Models     │
              │  SQLAlchemy    │
              │  (Postgres)    │
              └────────────────┘
```

## The three layers

### Core Engine (`src/taskstore/engine/`)

Immutable business rules. Not configurable at runtime.

- **`transitions.py`** — the state machine. Defines which transitions
  are valid (`TRIAGE → {BACKLOG, UNSTARTED, CANCELED}`, etc.). Every
  issue update runs through `is_valid_transition()`.
- **`audit.py`** — writes audit entries. `record_audit()` creates the
  row; `compute_diff()` produces the old-vs-new field map stored on
  update entries.
- **`defaults.py`** — seeds the six default workflow states
  (Triage, Backlog, Todo, In Progress, Done, Canceled) for every
  new team.

The engine layer has no concept of HTTP, teams, or authentication.
It is the "what this system guarantees" layer.

### Rules Engine (`src/taskstore/rules/`)

User-configurable server-side logic. Runs on every write that
matches a trigger.

- **`context.py`** — the `RuleContext` passed to conditions and
  actions. Carries the issue shape, current user, state transition
  info, and changed fields.
- **`conditions.py`** — pure evaluation of simple predicates:
  `field_equals`, `field_in`, `field_contains`, `field_gt`/`lt`,
  `label_has`, and composites (`and`, `or`, `not`).
- **`evaluator.py`** — orchestrates the full pipeline: load rules
  matching the trigger, evaluate conditions (including DB-backed
  `count_query` and `estimate_sum`), collect effects, apply them.
  Raises `RuleRejection` on `reject` actions and
  `RuleEvaluationError` on malformed rules.
- **`actions.py`** — the effect DSL. Supported actions: `reject`,
  `set_field` (whitelisted fields only), `add_label`, `add_comment`,
  `notify`. `validate_actions()` runs at rule-write time to catch
  structural errors early.

See [rules-engine.md](rules-engine.md) for the condition/action
reference.

### API (`src/taskstore/api/`)

Transport + auth + response formatting.

- **`deps.py`** — all auth and role gating. `get_team`,
  `get_current_user`, `verified_team`, `require_owner`,
  `require_admin_or_owner`, `verified_team_admin`. Every endpoint
  goes through one of these; manual auth checks are not allowed.
- **`errors.py`** — FastAPI exception handlers that wrap every
  response (success or error) into the same `Envelope` shape.
  Handles `HTTPException`, `RequestValidationError`,
  `RuleRejection`, `RuleEvaluationError`.
- **`<resource>.py`** — per-resource routers. Thin — they wire
  request → dep → service → response. Business logic lives in
  services, not here.
- **`setup.py`** — the one unauthenticated bootstrap endpoint.
  Refuses once any team exists.

## Services (`src/taskstore/services/`)

The glue between API and the engine + rules. Services own the
"what happens when" coordination:

- Validation that can't be expressed in Pydantic schemas (cross-
  tenant reference checks, role-dependent filters).
- Transaction boundaries (`db.commit()` / `db.rollback()`).
- Audit entry writes.
- Rule evaluation calls.

Services take SQLAlchemy sessions and domain types; they don't
speak HTTP.

## Auth model

Auth is **team-level via API key + actor declaration via header**.

- `X-API-Key` identifies the team. Stored as a SHA-256 hash; the
  plaintext is returned exactly once at team creation / setup.
- `X-User-Id` identifies which member is acting. The server
  verifies that UUID is a member of the authed team but does not
  authenticate the individual. In other words: team members share
  the API key; the header declares who among them made the request.
- Roles (OWNER / ADMIN / MEMBER) gate endpoints per the matrix
  in [api-reference.md](api-reference.md).

Consequences:
- Audit entries are non-repudiable at the team level, not the
  individual level. A holder of the API key can spoof any member's
  ID in audit.
- Rotating a team's API key requires re-creating the team (no
  rotation endpoint yet).

## Error contract

Every response has the same top-level shape:

```json
{"data": ..., "meta": ..., "errors": [...], "warnings": []}
```

- Success: `data` populated, `errors == []`
- Error: `data == null`, `errors` has ≥1 entry with at least a
  `message`. Rule errors additionally include `rule_id` / `rule_name`.

Enforced by the exception handlers in `api/errors.py` — any
`HTTPException`, pydantic validation error, or rule exception gets
rewrapped.

## Data model

See `src/taskstore/models/` for the ORM classes. Key relationships:

```
Team ─┬─► WorkflowState (6 defaults + custom)
      ├─► User (via TeamMembership w/ role)
      ├─► Project
      ├─► Issue ──► Label (via IssueLabel)
      │      └──► Comment
      ├─► Rule
      ├─► Notification
      └─► AuditEntry
```

Every row belongs to exactly one team. Cross-team references on
writes (e.g. an issue pointing at another team's project) are
blocked by `_validate_references()` in `issue_service.py`.

## Migration story

One migration for the initial schema, one for C2's API-key
hashing. Future migrations should preserve the pattern:

- Additive first (new column nullable, backfill, add constraints).
- Idempotent — re-runnable on a DB where the migration already
  ran.
- Test-covered — `tests/conftest.py` uses `create_all` rather than
  migrations, but every migration should be validated against a
  fresh container start (`docker compose up --build`).

## Why these layers

- **Engine is immutable.** State machine and audit shouldn't change
  at user request. Pushing them into a separate layer makes the
  contract obvious.
- **Rules are configurable.** Keeping them in their own layer with
  a schema-light DSL (JSONB conditions, JSONB actions) means
  product logic evolves without code changes.
- **API is transport-only.** Auth + response shaping + routing
  live here; business logic goes one layer down. Makes it easy to
  add non-HTTP entry points later (e.g. a message-queue consumer)
  without duplicating service logic.
