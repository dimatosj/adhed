# State Machine

Every issue in ADHED has exactly one workflow state. States belong to one of 6 fixed categories (types). You can create multiple named states within each category, but the transition rules are governed by the category, not the name.

## The 6 State Categories

| Category | Meaning |
|----------|---------|
| `triage` | Newly captured items awaiting evaluation. Not yet committed to. |
| `backlog` | Accepted work, but not yet scheduled or ready to start. |
| `unstarted` | Scheduled/ready work that has not begun. |
| `started` | Actively in progress. |
| `completed` | Done. Terminal state (but can be reopened). |
| `canceled` | Abandoned. Terminal state (but can be reopened). |

## Default States

When a team is created, these 6 states are seeded automatically:

| Name | Category | Position |
|------|----------|----------|
| Triage | `triage` | 0 |
| Backlog | `backlog` | 0 |
| Todo | `unstarted` | 0 |
| In Progress | `started` | 0 |
| Done | `completed` | 0 |
| Canceled | `canceled` | 0 |

You can add custom states to any category. For example, you might add "In Review" as a second `started` state with `position: 1`.

## Valid Transitions

Transitions are validated by **category**, not by state name. The table below shows which category an issue can move TO from each FROM category:

| From | Valid targets |
|------|-------------|
| `triage` | `backlog`, `unstarted`, `canceled` |
| `backlog` | `unstarted`, `triage`, `canceled` |
| `unstarted` | `started`, `backlog`, `canceled` |
| `started` | `completed`, `unstarted`, `backlog`, `canceled` |
| `completed` | `unstarted` |
| `canceled` | `backlog` |

### Same-category transitions always allowed

Moving an issue between two states within the same category is always valid. For example, moving from "In Progress" (`started`) to "In Review" (`started`) is always permitted because both states share the `started` category.

### Invalid transitions

Attempting an invalid transition returns HTTP 422:

```json
{"detail": "Invalid state transition: started -> triage"}
```

## Default State Assignment

When creating an issue without specifying `state_id`:

1. If the team has `triage_enabled: true` (the default), the issue is placed in the first `triage` state (ordered by position).
2. If triage is disabled, the issue is placed in the first `backlog` state.
3. If neither exists, the API returns HTTP 500.

To disable triage:

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/teams/$TEAM_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"settings": {"triage_enabled": false}}'
```

## Reopen Behavior

Terminal states have limited forward transitions for reopening:

- **Completed** can move to `unstarted` (re-open, needs rework)
- **Canceled** can move to `backlog` (re-open, reconsider)

This prevents accidentally moving completed work directly to "in progress" without going through the planning stage.

## Auto-Archive Behavior

Teams have an `archive_days` setting (default: 30). Issues in `completed` or `canceled` states for longer than this period are eligible for archiving. Archived issues:

- Have a non-null `archived_at` timestamp
- Are excluded from list queries by default (`archived=false`)
- Can still be retrieved by passing `?archived=true`

## Custom States Within Categories

You can add multiple states to any category to model your specific workflow:

```bash
source .adhed-credentials
# Add "In Review" as a started state
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/states" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "In Review", "type": "started", "position": 1}'

# Add "Waiting On" as a started state
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/states" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "Waiting On", "type": "started", "position": 2}'
```

All transition rules still apply by category. Moving from "In Review" (`started`) to "Done" (`completed`) is valid because `started -> completed` is valid.

## Transition Diagram

```
                    +-----------+
                    |  Triage   |
                    +-----+-----+
                          |
              +-----------+-----------+
              v                       v
        +-----------+           +-----------+
        |  Backlog  |<--------->| Canceled  |
        +-----+-----+           +-----------+
              |                       ^
              v                       |
        +-----------+                 |
        | Unstarted |<-------+--------+
        +-----+-----+        |
              |               |
              v               |
        +-----------+         |
        |  Started  |---------+
        +-----+-----+
              |
              v
        +-----------+
        | Completed |
        +-----------+
```

Arrows show forward progression. Backward/lateral transitions (reopen, cancel) follow the table above.
