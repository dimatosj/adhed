# API Reference

Base URL: `http://localhost:8100`

All responses use the [Envelope format](#response-envelope). Authentication is via headers — see [Authentication](#authentication).

---

## Authentication

| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | Always | Team API key (returned from `/api/v1/setup`) |
| `X-User-Id` | For mutations | UUID of the acting user |

Read-only endpoints (GET) only require `X-API-Key`. Mutations (POST, PATCH, DELETE) also require `X-User-Id`.

---

## Response Envelope

Every response is wrapped in:

```json
{
  "data": <T>,
  "meta": { "total": 0, "limit": 50, "offset": 0 },
  "errors": [],
  "warnings": []
}
```

- `data` — the response payload (object or array)
- `meta` — pagination info (present on list endpoints)
- `errors` — array of `{ "rule_id": "...", "rule_name": "...", "message": "..." }` (present on rule rejections, HTTP 422)
- `warnings` — informational messages

---

## Setup

### POST /api/v1/setup

Creates the initial team and owner user. Call once after first deploy.

**Auth:** None required.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_name` | string | yes | Display name for the team |
| `team_key` | string | yes | Short key (uppercase letters, used in issue prefixes) |
| `user_name` | string | yes | Name of the owner user |
| `user_email` | string | yes | Email of the owner user |
| `include_default_labels` | boolean | no | Seed 14 GTD-style default labels (default: `false`) |

**Response (201):** The response includes `api_key` **exactly once** —
record it, you cannot recover it later (keys are SHA-256 hashed at rest).

```json
{
  "team_id": "uuid",
  "team_name": "Home",
  "team_key": "HOME",
  "api_key": "adhed_...",
  "user_id": "uuid",
  "user_name": "Jane",
  "user_email": "jane@example.com"
}
```

**Example:**

```bash
curl -s -X POST "http://localhost:8100/api/v1/setup" \
  -H "Content-Type: application/json" \
  -d '{"team_name": "Home", "team_key": "HOME", "user_name": "Jane", "user_email": "jane@example.com"}'
```

---

## Health

### GET /api/v1/health

Returns API health status.

**Auth:** None required.

**Response (200):**

```json
{"status": "ok"}
```

**Example:**

```bash
curl -s "http://localhost:8100/api/v1/health"
```

---

## Teams

### POST /api/v1/teams

Create an additional team. The first team must be created via
[`/api/v1/setup`](#setup).

**Auth:** X-API-Key + X-User-Id (caller must be an OWNER of an
existing team). Returns `403` if the caller is not an OWNER.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Team display name |
| `key` | string | yes | Short team key |

**Response (201):** `Envelope[TeamCreateResponse]`. The response
includes `api_key` **exactly once** — record it, you cannot recover
it later (keys are SHA-256 hashed at rest).

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{"name": "Work", "key": "WORK"}'
```

### GET /api/v1/teams/{team_id}

Get team details.

**Auth:** X-API-Key

**Response (200):** `Envelope[TeamResponse]`

TeamResponse fields: `id`, `name`, `key`, `settings` (`archive_days`, `triage_enabled`), `created_at`, `updated_at`. The API key is intentionally **not** returned — it is shown only at creation time.

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID" \
  -H "X-API-Key: $API_KEY"
```

### PATCH /api/v1/teams/{team_id}

Update team settings.

**Auth:** X-API-Key

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | no | New team name |
| `settings` | object | no | `{ "archive_days": 30, "triage_enabled": true }` |

**Response (200):** `Envelope[TeamResponse]`

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/teams/$TEAM_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"settings": {"triage_enabled": false, "archive_days": 60}}'
```

---

## Users

### POST /api/v1/teams/{team_id}/users

Create a user and add them to the team.

**Auth:** X-API-Key

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | User display name |
| `email` | string | yes | User email |
| `role` | string | no | `owner`, `admin`, or `member` (default: `member`) |

**Response (201):** `Envelope[UserResponse]`

UserResponse fields: `id`, `name`, `email`, `role`, `created_at`.

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/users" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "Alex", "email": "alex@example.com", "role": "member"}'
```

### GET /api/v1/teams/{team_id}/users

List all team members.

**Auth:** X-API-Key

**Response (200):** `Envelope[list[UserResponse]]`

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/users" \
  -H "X-API-Key: $API_KEY"
```

---

## Workflow States

### GET /api/v1/teams/{team_id}/states

List all workflow states for the team, ordered by type and position.

**Auth:** X-API-Key

**Response (200):** `Envelope[list[WorkflowStateResponse]]`

WorkflowStateResponse fields: `id`, `team_id`, `name`, `type` (one of: `triage`, `backlog`, `unstarted`, `started`, `completed`, `canceled`), `color`, `position`, `created_at`.

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/states" \
  -H "X-API-Key: $API_KEY"
```

### POST /api/v1/teams/{team_id}/states

Create a custom workflow state.

**Auth:** X-API-Key

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | State display name |
| `type` | string | yes | Category: `triage`, `backlog`, `unstarted`, `started`, `completed`, `canceled` |
| `color` | string | no | Hex color code |
| `position` | int | no | Sort order within category (default: 0) |

**Response (201):** `Envelope[WorkflowStateResponse]`

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/states" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "In Review", "type": "started", "color": "#8b5cf6", "position": 1}'
```

---

## Labels

### POST /api/v1/teams/{team_id}/labels

Create a label.

**Auth:** X-API-Key

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Label name |
| `color` | string | no | Hex color code |
| `description` | string | no | Label description |

**Response (201):** `Envelope[LabelResponse]`

LabelResponse fields: `id`, `team_id`, `name`, `color`, `description`, `created_at`.

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/labels" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "urgent", "color": "#ef4444"}'
```

### GET /api/v1/teams/{team_id}/labels

List all labels for the team.

**Auth:** X-API-Key

**Response (200):** `Envelope[list[LabelResponse]]`

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/labels" \
  -H "X-API-Key: $API_KEY"
```

### PATCH /api/v1/labels/{label_id}

Update a label.

**Auth:** X-API-Key

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | no | New label name |
| `color` | string | no | New color |
| `description` | string | no | New description |

**Response (200):** `Envelope[LabelResponse]`

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/labels/$LABEL_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"color": "#f59e0b"}'
```

### DELETE /api/v1/labels/{label_id}

Delete a label.

**Auth:** X-API-Key

**Response:** 204 No Content

```bash
source .adhed-credentials
curl -s -X DELETE "http://localhost:8100/api/v1/labels/$LABEL_ID" \
  -H "X-API-Key: $API_KEY"
```

---

## Projects

### POST /api/v1/teams/{team_id}/projects

Create a project.

**Auth:** X-API-Key

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Project name |
| `description` | string | no | Project description |
| `state` | string | no | `planned` (default), `started`, `paused`, `completed`, `canceled` |
| `lead_id` | uuid | no | User ID of the project lead |

**Response (201):** `Envelope[ProjectResponse]`

ProjectResponse fields: `id`, `team_id`, `name`, `description`, `state`, `lead_id`, `created_at`, `updated_at`, `issue_counts` (`triage`, `backlog`, `unstarted`, `started`, `completed`, `canceled`).

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/projects" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "Kitchen Renovation", "description": "All kitchen-related tasks"}'
```

### GET /api/v1/teams/{team_id}/projects

List projects.

**Auth:** X-API-Key

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `state` | string | Filter by project state: `planned`, `started`, `paused`, `completed`, `canceled` |
| `lead_id` | uuid | Filter by project lead |

**Response (200):** `Envelope[list[ProjectResponse]]`

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/projects?state=started" \
  -H "X-API-Key: $API_KEY"
```

### GET /api/v1/projects/{project_id}

Get a single project with issue counts.

**Auth:** X-API-Key

**Response (200):** `Envelope[ProjectResponse]`

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/projects/$PROJECT_ID" \
  -H "X-API-Key: $API_KEY"
```

### PATCH /api/v1/projects/{project_id}

Update a project.

**Auth:** X-API-Key

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | no | New name |
| `description` | string | no | New description |
| `state` | string | no | New project state |
| `lead_id` | uuid | no | New lead user |

**Response (200):** `Envelope[ProjectResponse]`

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/projects/$PROJECT_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"state": "started"}'
```

### DELETE /api/v1/projects/{project_id}

Delete a project.

**Auth:** X-API-Key

**Response:** 204 No Content

```bash
source .adhed-credentials
curl -s -X DELETE "http://localhost:8100/api/v1/projects/$PROJECT_ID" \
  -H "X-API-Key: $API_KEY"
```

---

## Issues

### POST /api/v1/teams/{team_id}/issues

Create a single issue.

**Auth:** X-API-Key, X-User-Id

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | yes | Issue title |
| `description` | string | no | Markdown description |
| `type` | string | no | `task` (default), `reference`, `idea` |
| `priority` | int | no | 0 (none) to 4 (highest). Default: 0 |
| `estimate` | int | no | Effort estimate (arbitrary units) |
| `state_id` | uuid | no | Initial state (defaults to Triage or Backlog) |
| `assignee_id` | uuid | no | Assigned user |
| `project_id` | uuid | no | Parent project |
| `parent_id` | uuid | no | Parent issue (for subtasks) |
| `due_date` | date | no | Due date (YYYY-MM-DD) |
| `custom_fields` | object | no | Arbitrary key-value pairs |
| `label_ids` | list[uuid] | no | Label IDs to attach at creation |

**Response (201):** `Envelope[IssueResponse]`

IssueResponse fields: `id`, `team_id`, `title`, `description`, `type`, `priority`, `estimate`, `state` (`id`, `name`, `type`), `assignee_id`, `project_id`, `parent_id`, `due_date`, `custom_fields`, `created_by`, `created_at`, `updated_at`, `archived_at`, `labels` (list of `{id, name}`).

Rules with trigger `issue.created` are evaluated. On rejection, returns 422 with `errors` array.

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/issues" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{"title": "Fix leaking faucet", "priority": 3, "due_date": "2026-04-15"}'
```

### POST /api/v1/teams/{team_id}/issues/batch

Create multiple issues in one request. Each item is processed independently — a rule rejection on one does not fail the batch.

**Auth:** X-API-Key, X-User-Id

**Request body:** Array of `IssueCreate` objects (same schema as single create).

**Response (200):** `Envelope[list]` where each item is `{"data": IssueResponse | null, "error": string | null}`.

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/issues/batch" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '[
    {"title": "Buy groceries", "priority": 2},
    {"title": "Schedule dentist", "priority": 1},
    {"title": "Clean garage", "priority": 3}
  ]'
```

### PATCH /api/v1/teams/{team_id}/issues/batch

Bulk-update issues matching a filter.

**Auth:** X-API-Key, X-User-Id

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filter` | object | yes | Filter criteria: `state_type`, `assignee_id`, `project_id`, `priority` |
| `update` | object | yes | Fields to update (same as single PATCH) |

**Response (200):** `Envelope[list[IssueResponse]]`

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/teams/$TEAM_ID/issues/batch" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{"filter": {"state_type": "triage"}, "update": {"priority": 2}}'
```

### GET /api/v1/teams/{team_id}/issues

List issues with filtering, sorting, and pagination.

**Auth:** X-API-Key

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `state_type` | string | — | Comma-separated state types: `triage`, `backlog`, `unstarted`, `started`, `completed`, `canceled` |
| `assignee` | uuid | — | Filter by assignee user ID |
| `project_id` | string | — | Filter by project ID. Use `"null"` for issues without a project |
| `parent_id` | string | — | Filter by parent issue ID. Use `"null"` for top-level issues |
| `label` | string | — | Comma-separated label names. AND logic: issue must have ALL specified labels |
| `priority` | string | — | Comma-separated priority values (e.g. `1,2`) |
| `type` | string | — | Issue type: `task`, `reference`, `idea` |
| `created_by` | uuid | — | Filter by creator user ID |
| `due_before` | date | — | Issues due before this date (YYYY-MM-DD) |
| `due_after` | date | — | Issues due after this date (YYYY-MM-DD) |
| `overdue` | bool | — | If `true`, only issues past due date and not in completed/canceled state |
| `title_search` | string | — | Full-text search on issue titles |
| `estimate_lte` | int | — | Estimate less than or equal to |
| `estimate_gte` | int | — | Estimate greater than or equal to |
| `archived` | bool | `false` | If `true`, include archived issues |
| `limit` | int | `50` | Max results (capped at 200) |
| `offset` | int | `0` | Skip N results |
| `sort` | string | `created_at` | Sort field: `created_at`, `updated_at`, `priority`, `due_date` |
| `order` | string | `desc` | Sort order: `asc` or `desc` |

**Response (200):** `Envelope[list[IssueResponse]]` with `meta.total` for total count.

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/issues?state_type=started,unstarted&priority=1,2&sort=priority&order=desc&limit=10" \
  -H "X-API-Key: $API_KEY"
```

### GET /api/v1/issues/{issue_id}

Get a single issue.

**Auth:** X-API-Key

**Response (200):** `Envelope[IssueResponse]`

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/issues/$ISSUE_ID" \
  -H "X-API-Key: $API_KEY"
```

### PATCH /api/v1/issues/{issue_id}

Update an issue. Triggers state transition validation and rule evaluation.

**Auth:** X-API-Key, X-User-Id

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | no | New title |
| `description` | string | no | New description |
| `type` | string | no | `task`, `reference`, `idea` |
| `priority` | int | no | 0-4 |
| `estimate` | int | no | Effort estimate |
| `state_id` | uuid | no | Target state (validated against transition rules) |
| `assignee_id` | uuid | no | New assignee |
| `project_id` | uuid | no | New project |
| `due_date` | date | no | New due date |
| `custom_fields` | object | no | Merge with existing custom fields |

Rules evaluated: `issue.state_changed` (if state changes), `issue.assigned` (if assignee changes), `issue.updated` (always).

**Response (200):** `Envelope[IssueResponse]`

On rule rejection: **422** with `errors` array.

On invalid transition: **422** with `detail: "Invalid state transition: started -> triage"`.

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/issues/$ISSUE_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{"priority": 1, "assignee_id": "'$USER_ID'"}'
```

### DELETE /api/v1/issues/{issue_id}

Delete an issue. Fails with 409 if the issue has active (non-completed, non-canceled) subtasks.

**Auth:** X-API-Key, X-User-Id

**Response:** 204 No Content

```bash
source .adhed-credentials
curl -s -X DELETE "http://localhost:8100/api/v1/issues/$ISSUE_ID" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID"
```

### POST /api/v1/issues/{issue_id}/convert-to-project

Convert an issue into a project. Creates a new project with the issue's title and description, then assigns the issue to the new project.

**Auth:** X-API-Key

**Response (201):** `Envelope[{ "project": ProjectResponse, "issue": IssueResponse }]`

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/issues/$ISSUE_ID/convert-to-project" \
  -H "X-API-Key: $API_KEY"
```

---

## Comments

### POST /api/v1/issues/{issue_id}/comments

Add a comment to an issue.

**Auth:** X-API-Key, X-User-Id

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `body` | string | yes | Comment text |

**Response (201):** `Envelope[CommentResponse]`

CommentResponse fields: `id`, `issue_id`, `user_id`, `body`, `created_at`, `updated_at`.

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/issues/$ISSUE_ID/comments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{"body": "Called and scheduled for next Tuesday."}'
```

### GET /api/v1/issues/{issue_id}/comments

List all comments on an issue.

**Auth:** X-API-Key

**Response (200):** `Envelope[list[CommentResponse]]`

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/issues/$ISSUE_ID/comments" \
  -H "X-API-Key: $API_KEY"
```

---

## Rules

### POST /api/v1/teams/{team_id}/rules

Create an automation rule.

**Auth:** X-API-Key

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Rule name |
| `description` | string | no | Human-readable description |
| `trigger` | string | yes | See [Rules Engine](rules-engine.md) for triggers |
| `conditions` | object | yes | Condition tree (see Rules Engine docs) |
| `actions` | list or object | yes | Action(s) to execute |
| `priority` | int | no | Evaluation order (lower = first, default: 100) |
| `enabled` | bool | no | Default: true |

Triggers: `issue.created`, `issue.state_changed`, `issue.assigned`, `issue.updated`, `issue.comment_added`, `project.state_changed`.

**Response (201):** `Envelope[RuleResponse]`

RuleResponse fields: `id`, `team_id`, `name`, `description`, `enabled`, `trigger`, `conditions`, `actions`, `priority`, `created_at`, `updated_at`.

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/rules" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "name": "WIP limit",
    "trigger": "issue.state_changed",
    "conditions": {
      "type": "count_query",
      "where": {"state_type": ["started"], "assignee": "$current_user"},
      "operator": ">=",
      "value": 5
    },
    "actions": [{"type": "reject", "message": "WIP limit reached (max 5 in progress)"}]
  }'
```

### GET /api/v1/teams/{team_id}/rules

List all rules for the team.

**Auth:** X-API-Key

**Response (200):** `Envelope[list[RuleResponse]]`

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/rules" \
  -H "X-API-Key: $API_KEY"
```

### PATCH /api/v1/rules/{rule_id}

Update a rule.

**Auth:** X-API-Key

**Request body:** Same fields as create, all optional.

**Response (200):** `Envelope[RuleResponse]`

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/rules/$RULE_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"enabled": false}'
```

### DELETE /api/v1/rules/{rule_id}

Delete a rule.

**Auth:** X-API-Key

**Response:** 204 No Content

```bash
source .adhed-credentials
curl -s -X DELETE "http://localhost:8100/api/v1/rules/$RULE_ID" \
  -H "X-API-Key: $API_KEY"
```

---

## Notifications

### GET /api/v1/teams/{team_id}/notifications

List unread notifications for the team (or a specific user).

**Auth:** X-API-Key

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `user_id` | uuid | Filter notifications for a specific user |

**Response (200):** `Envelope[list[NotificationResponse]]`

NotificationResponse fields: `id`, `team_id`, `user_id`, `rule_id`, `issue_id`, `message`, `read`, `created_at`.

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/notifications?user_id=$USER_ID" \
  -H "X-API-Key: $API_KEY"
```

### POST /api/v1/notifications/{notification_id}/read

Mark a single notification as read.

**Auth:** X-API-Key

**Response (200):** `Envelope[NotificationResponse]`

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/notifications/$NOTIFICATION_ID/read" \
  -H "X-API-Key: $API_KEY"
```

### POST /api/v1/teams/{team_id}/notifications/read-all

Mark all unread notifications for the team as read.

**Auth:** X-API-Key

**Response (200):** `Envelope[{"marked_all_read": true}]`

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/notifications/read-all" \
  -H "X-API-Key: $API_KEY"
```

---

## Audit

### GET /api/v1/teams/{team_id}/audit

List audit trail entries with filtering and pagination.

**Auth:** X-API-Key

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `entity_type` | string | — | Filter by entity type (e.g. `issue`, `project`) |
| `entity_id` | uuid | — | Filter by specific entity |
| `action` | string | — | `create`, `update`, `delete` |
| `user_id` | uuid | — | Filter by acting user |
| `after` | datetime | — | Entries after this timestamp |
| `before` | datetime | — | Entries before this timestamp |
| `limit` | int | `50` | Max results |
| `offset` | int | `0` | Skip N results |

**Response (200):** `Envelope[list[AuditResponse]]`

AuditResponse fields: `id`, `team_id`, `entity_type`, `entity_id`, `action`, `user_id`, `changes` (diff object with `{field: {old, new}}`), `created_at`.

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/audit?entity_type=issue&limit=10" \
  -H "X-API-Key: $API_KEY"
```

---

## Summary

### GET /api/v1/teams/{team_id}/summary

Get a dashboard summary: triage count, overdue items, due soon items, stalled projects, counts by state type and assignee, recently completed items, and waiting-for items.

**Auth:** X-API-Key (optionally X-User-Id for user-scoped summaries)

**Response (200):** `Envelope[SummaryData]`

SummaryData fields:

| Field | Type | Description |
|-------|------|-------------|
| `triage_count` | int | Number of items in triage |
| `overdue` | list | `[{id, title, due_date, days_overdue}]` |
| `due_soon` | list | `[{id, title, due_date, days_until}]` |
| `stalled_projects` | list | `[{id, name, backlog_count, days_since_activity}]` |
| `by_state_type` | object | `{"started": 3, "unstarted": 7, ...}` |
| `by_assignee` | object | `{"user-id": {"started": 2, "unstarted": 1}}` |
| `recently_completed` | list | `[{id, title, completed_at}]` |
| `waiting_for` | list | `[{id, title, assignee, created_by}]` |

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/summary" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID"
```
