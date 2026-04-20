# Getting Started

This guide walks you through setting up ADHED and making your first API calls.

## Prerequisites

- **Docker** (with Docker Compose) — [install Docker Desktop](https://docs.docker.com/get-docker/)
- **curl** (included on macOS and most Linux distros)

## Setup

### With Claude Code (recommended)

```bash
git clone https://github.com/dimatosj/adhed.git
cd adhed
claude
```

Claude will walk you through setup interactively — it checks Docker, prompts for your name/email/team, starts services, and saves credentials.

### Without Claude Code

```bash
git clone https://github.com/dimatosj/adhed.git
cd adhed
./setup.sh
```

The setup script will:
1. Verify Docker is running
2. Prompt for your name, email, and team name
3. Start Postgres and the API via `docker compose up -d`
4. Call the `/api/v1/setup` endpoint to create your team and user
5. Save credentials to `.adhed-credentials`

After setup, your credentials file looks like:

```
API_KEY=adhed_abc123...
USER_ID=550e8400-e29b-41d4-a716-446655440000
TEAM_ID=660e8400-e29b-41d4-a716-446655440001
URL=http://localhost:8100
```

## First API Call: Create an Issue

All examples use `source .adhed-credentials` to load your credentials as shell variables.

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/issues" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{"title": "Call the dentist", "priority": 2}'
```

Response:

```json
{
  "data": {
    "id": "...",
    "team_id": "...",
    "title": "Call the dentist",
    "priority": 2,
    "type": "task",
    "state": { "id": "...", "name": "Triage", "type": "triage" },
    "labels": [],
    "created_at": "..."
  },
  "meta": null,
  "errors": [],
  "warnings": []
}
```

New issues default to the **Triage** state (or Backlog if triage is disabled in team settings).

## List Issues

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/issues" \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
```

Filter by state type:

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/issues?state_type=triage" \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
```

## Move an Issue Through States

Issues follow a state machine. Before moving an issue, look up your team's state IDs:

### Step 1: List workflow states

```bash
source .adhed-credentials
curl -s "http://localhost:8100/api/v1/teams/$TEAM_ID/states" \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
```

You will see something like:

```json
{
  "data": [
    { "id": "aaa...", "name": "Triage", "type": "triage" },
    { "id": "bbb...", "name": "Backlog", "type": "backlog" },
    { "id": "ccc...", "name": "Todo", "type": "unstarted" },
    { "id": "ddd...", "name": "In Progress", "type": "started" },
    { "id": "eee...", "name": "Done", "type": "completed" },
    { "id": "fff...", "name": "Canceled", "type": "canceled" }
  ]
}
```

### Step 2: Move from Triage to Backlog

Replace `ISSUE_ID` and `BACKLOG_STATE_ID` with actual UUIDs from the previous responses:

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/issues/$ISSUE_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d "{\"state_id\": \"$BACKLOG_STATE_ID\"}"
```

### Step 3: Move to In Progress

```bash
source .adhed-credentials
curl -s -X PATCH "http://localhost:8100/api/v1/issues/$ISSUE_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d "{\"state_id\": \"$IN_PROGRESS_STATE_ID\"}"
```

Not all transitions are valid. See [State Machine](state-machine.md) for the full transition table.

## Create Your First Rule: Auto-Label by Keyword

Rules run automatically on every write operation. This example adds a "health" label to any issue whose title contains "dentist".

### Step 1: Create the label

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/labels" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "health", "color": "#10b981"}'
```

### Step 2: Create the rule

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/rules" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "name": "Auto-label health",
    "trigger": "issue.created",
    "conditions": {
      "type": "or",
      "conditions": [
        {"type": "field_contains", "field": "title", "value": "dentist"},
        {"type": "field_contains", "field": "title", "value": "doctor"},
        {"type": "field_contains", "field": "title", "value": "gym"}
      ]
    },
    "actions": [{"type": "add_label", "label": "health"}]
  }'
```

### Step 3: Test it

```bash
source .adhed-credentials
curl -s -X POST "http://localhost:8100/api/v1/teams/$TEAM_ID/issues" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{"title": "Book dentist appointment", "priority": 2}'
```

The response will include `"labels": [{"name": "health", ...}]` automatically applied by the rule.

## Next Steps

- [API Reference](api-reference.md) — all endpoints, parameters, and response shapes
- [State Machine](state-machine.md) — the 6 state categories and valid transitions
- [Rules Engine](rules-engine.md) — triggers, conditions, actions, and examples
- [Integration Guide](integration-guide.md) — building clients, CLI tools, and chat integrations
