# Recurrences — Design Spec

*2026-05-06*

## Purpose

Add recurring task support to ADHED. A recurrence is a rule that spawns a new issue into backlog on a schedule (cron or interval). Spawned issues are regular issues with configurable defaults. A dedicated scheduler service checks for due recurrences and creates instances.

## Scope

### In scope
- Recurrences table with schedule expression (cron or interval), title template, issue defaults
- CRUD API endpoints for recurrences
- Scheduler service (separate container) that polls for due recurrences and spawns issues
- Title template substitution (`{date}` replaced with due date)
- Pause/resume via active flag

### Out of scope
- Workflow-specific interpretation of spawned issues (consumers define their own custom_fields semantics)
- Timezone-aware scheduling (UTC only for v1)
- Catch-up spawning for missed runs (if scheduler was down, only spawn the next due instance, not all missed ones)

## Data Model

### `recurrences` table

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| team_id | UUID FK → teams | |
| created_by | UUID FK → users | |
| title_template | String(500) | Supports `{date}` substitution |
| description_template | Text, nullable | |
| issue_defaults | JSONB | priority, project_id, assignee_id, custom_fields, label_ids |
| schedule_type | String(20) | `cron` or `interval` |
| schedule_expr | String(100) | Cron: `0 9 1 */3 *`, Interval: `90d`, `7d`, `2w` |
| next_due_at | DateTime | When next instance should spawn (UTC) |
| last_spawned_at | DateTime, nullable | When last instance was created |
| last_spawned_issue_id | UUID FK → issues, nullable | Most recent spawned issue |
| active | Boolean, default true | Pause/resume |
| created_at | DateTime | |
| updated_at | DateTime | |

### Indexes
- `ix_recurrences_team` on (team_id)
- `ix_recurrences_due` on (active, next_due_at) — scheduler query

## API Endpoints

### POST /api/v1/teams/{team_id}/recurrences (201)
Create a recurrence. Computes `next_due_at` from schedule expression.

Request:
```json
{
  "title_template": "Change air filters",
  "description_template": "Check and replace HVAC filters",
  "issue_defaults": {
    "priority": 2,
    "custom_fields": {"category": "maintenance"}
  },
  "schedule_type": "interval",
  "schedule_expr": "90d",
  "next_due_at": "2026-07-01T09:00:00Z"
}
```

`next_due_at` is optional on create — if omitted, computed as now + interval or next cron occurrence.

### GET /api/v1/teams/{team_id}/recurrences (200)
List recurrences. Filters: `?active=true`, `?schedule_type=cron`.

### GET /api/v1/recurrences/{recurrence_id} (200)
Get single recurrence.

### PATCH /api/v1/recurrences/{recurrence_id} (200)
Update recurrence. Setting `active: false` pauses, `active: true` resumes. Changing schedule_expr recomputes next_due_at.

### DELETE /api/v1/recurrences/{recurrence_id} (204)
Delete recurrence.

## Scheduler Service

Runs as a separate container (`adhed-scheduler`) using the same Docker image with a different entrypoint: `python -m taskstore.scheduler`.

### Behavior
1. Every 60 seconds, query: `SELECT * FROM recurrences WHERE active = true AND next_due_at <= now()`
2. For each due recurrence:
   a. Create a new issue using `issue_defaults`, with title from `title_template` (`{date}` → due date formatted as YYYY-MM-DD)
   b. Issue is created in the team's default backlog state
   c. Set `last_spawned_at = now()`, `last_spawned_issue_id = new_issue.id`
   d. Advance `next_due_at` based on schedule_type:
      - interval: `next_due_at += interval`
      - cron: compute next occurrence from croniter
   e. Record audit entry for the spawn
3. Each spawn is its own transaction — one failure doesn't block others

### Missed runs
If the scheduler was down and next_due_at is in the past, spawn exactly one instance and advance to the next future due date. No catch-up flood.

### Dependencies
- `croniter` for cron expression parsing and next-occurrence computation
- Reuses existing `create_issue` service (or a lightweight version that skips rules evaluation)

## Interval Expression Format

Simple duration strings:
- `Nd` — every N days (e.g. `90d`, `7d`, `1d`)
- `Nw` — every N weeks (e.g. `2w`)
- `Nm` — every N months (e.g. `3m`)

Parsed internally to timedelta (days/weeks) or relativedelta (months).

## Spawned Issues

Regular issues. No special type or parent_id relationship. The link back to the recurrence is via `recurrences.last_spawned_issue_id`. If you need the full spawn history, query issues by creation audit entries with entity_type `recurrence_spawn`.

## Docker Compose Addition

```yaml
adhed-scheduler:
  build: .
  command: python -m taskstore.scheduler
  environment:
    - DATABASE_URL=postgresql+asyncpg://adhed:adhed@adhed-db:5432/adhed
    - DATABASE_URL_SYNC=postgresql://adhed:adhed@adhed-db:5432/adhed
    - LOG_LEVEL=${LOG_LEVEL:-info}
  depends_on:
    adhed-db:
      condition: service_healthy
  restart: unless-stopped
```

## Testing Strategy

- Unit tests for interval parsing (90d, 2w, 3m)
- Unit tests for cron next-occurrence computation
- Unit tests for title template substitution
- Integration tests for recurrence CRUD endpoints
- Integration test for scheduler spawn logic (create recurrence, advance time, verify issue created)
- Test missed run behavior (next_due_at in the past → one spawn, advance to future)
- Test pause/resume (active=false skips, active=true resumes)
