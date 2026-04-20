# Integration Guide

This guide covers how to build clients that talk to ADHED, with a case study of the NanoClaw `life-cli.py` integration.

---

## Authentication

Every request requires the `X-API-Key` header. Mutations additionally require `X-User-Id`.

```
X-API-Key: adhed_abc123...       # identifies the team
X-User-Id: 550e8400-...          # identifies the acting user (for audit trail)
```

The API key is team-scoped. There is no per-user authentication — the API trusts the `X-User-Id` header. This is by design: ADHED is meant for trusted environments (your own agents, CLI tools, internal bots), not public-facing applications.

---

## Response Envelope Format

Every response follows this structure (from `schemas/common.py`):

```json
{
  "data": <payload>,
  "meta": {"total": 42, "limit": 50, "offset": 0},
  "errors": [{"rule_id": "...", "rule_name": "...", "message": "..."}],
  "warnings": ["..."]
}
```

- **`data`** — always present. The response payload (object, array, or null on error).
- **`meta`** — present on list endpoints. Contains `total` (full count), `limit`, and `offset`.
- **`errors`** — non-empty only on rule rejections (HTTP 422). Each error has `rule_id`, `rule_name`, and `message`.
- **`warnings`** — informational messages that do not block the operation.

### Handling rule rejections

When a rule rejects an operation, you get HTTP 422 with the errors array populated:

```json
{
  "data": null,
  "errors": [
    {
      "rule_id": "abc-123",
      "rule_name": "WIP limit (5)",
      "message": "WIP limit reached — you already have 5 items in progress"
    }
  ]
}
```

Your client should:
1. Check for HTTP 422
2. Parse the `errors` array from the response
3. Display the `message` to the user (it explains what went wrong and what to do)
4. The `rule_name` helps identify which rule caused the rejection

---

## Pagination

List endpoints support `limit` and `offset` query parameters:

```
GET /api/v1/teams/{team_id}/issues?limit=20&offset=40
```

The response `meta` contains `total` for the full count:

```json
{"meta": {"total": 142, "limit": 20, "offset": 40}}
```

To paginate:
- Start with `offset=0`
- Increment offset by `limit` until `offset >= meta.total`
- Maximum `limit` for issues is 200

---

## Building a CLI Client

The reference CLI client is `life-cli.py` (in `integrations/nanoclaw/life/`). It demonstrates every pattern you need.

### Architecture

`life-cli.py` is a single-file Python script with no external dependencies (uses only `urllib`, `json`, `sys`, `os`). This makes it easy to deploy inside containers and restricted environments.

### Configuration from environment

```python
TASKSTORE_URL = os.environ.get("TASKSTORE_URL", "http://host.docker.internal:8100")
TASKSTORE_API_KEY = os.environ.get("TASKSTORE_API_KEY", "")
TASKSTORE_USER_ID = os.environ.get("TASKSTORE_USER_ID", "")
TASKSTORE_TEAM_ID = os.environ.get("TASKSTORE_TEAM_ID", "")
```

### Auth headers

The client builds headers once and reuses them:

```python
def _headers():
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if TASKSTORE_API_KEY:
        h["X-API-Key"] = TASKSTORE_API_KEY
    if TASKSTORE_USER_ID:
        h["X-User-Id"] = TASKSTORE_USER_ID
    return h
```

### The _team_path() pattern

ADHED has two URL patterns:
- **Team-scoped** resources: `/api/v1/teams/{team_id}/issues`, `/api/v1/teams/{team_id}/states`, etc.
- **Entity-scoped** resources: `/api/v1/issues/{id}`, `/api/v1/projects/{id}`, `/api/v1/rules/{id}`, etc.

`life-cli.py` handles this with a single routing function:

```python
def _team_path(path: str) -> str:
    team_id = get_team_id()
    # Entity-level paths (no team prefix needed)
    entity_prefixes = ("/issues/", "/projects/", "/rules/", "/notifications/")
    if any(path.startswith(p) for p in entity_prefixes):
        return f"/api/v1{path}"
    # Team-scoped paths
    return f"/api/v1/teams/{team_id}{path}"
```

This means the CLI can use short paths:
- `api_get("/issues")` becomes `GET /api/v1/teams/{team_id}/issues`
- `api_patch("/issues/abc-123", body)` becomes `PATCH /api/v1/issues/abc-123`

### State name resolution

Users want to say "move to In Progress", not pass UUIDs. The CLI resolves state names:

```python
def resolve_state_id(name: str) -> Optional[str]:
    states = get_states()  # cached after first call
    nl = name.lower()
    for s in states:
        if s.get("name", "").lower() == nl:
            return s.get("id")
    # Partial match fallback
    for s in states:
        if nl in s.get("name", "").lower():
            return s.get("id")
    return None
```

This allows `--state "progress"` to match "In Progress".

### Error handling

The CLI catches HTTP errors and prints the message, then exits non-zero:

```python
except urllib.error.HTTPError as e:
    raw = e.read()
    err = json.loads(raw)
    msg = err.get("error") or err.get("message") or str(err)
    print(f"API error {e.code}: {msg}", file=sys.stderr)
    sys.exit(1)
```

---

## Tips for Chat-Driven Interfaces

If you are building a chat bot or AI agent that manages tasks through conversation:

### Dedicated rooms per concern

Create separate chat rooms/channels for different contexts:
- A "Tasks" room for task management
- A "Projects" room for project planning
- Keep task operations out of general conversation

This gives the agent clear context about what the user wants.

### Deterministic CLIs over AI improvisation

Do not let the AI agent make raw HTTP calls to the API. Instead:

1. Provide a CLI script (like `life-cli.py`) with fixed commands
2. The AI agent calls the CLI, reads the output, and formats it for the user
3. This prevents hallucinated endpoints, malformed requests, and inconsistent behavior

The CLI acts as a contract between the AI and the API.

### The SKILL.md allowed-tools pattern

In NanoClaw, agent capabilities are declared in SKILL.md files:

```yaml
---
name: life
description: Manage tasks via the taskstore API.
allowed-tools: Bash(python3 /workspace/group/.claude/skills/life/life-cli.py *)
---
```

The `allowed-tools` field restricts what the agent can execute. It can only call `life-cli.py` with arguments — not curl, not arbitrary Python. This is defense-in-depth: even if the AI tries to improvise, the tool sandbox prevents it.

### Command structure

Design your CLI commands to be discoverable:

```
life-cli.py <resource> <action> [args]
```

Examples:
- `life-cli.py issue create --title "..." --priority 2`
- `life-cli.py issue list --state-type started --assignee me`
- `life-cli.py project stalled`
- `life-cli.py summary`

The AI agent can learn this structure from the SKILL.md documentation and use it reliably.

### Handling state by name (not ID)

Users in chat say "move it to in progress", not "set state_id to abc-123". Your CLI should:

1. Accept state names: `--state "In Progress"`
2. Resolve to UUIDs internally via the states list endpoint
3. Support partial matching for convenience

### Assignee shortcuts

Support `--assignee me` as a shortcut for the current user's UUID:

```python
def resolve_assignee(val: str) -> str:
    if val.lower() == "me":
        return TASKSTORE_USER_ID
    return val
```

---

## Client Checklist

When building a new ADHED client:

- [ ] Read credentials from environment or config file (never hardcode)
- [ ] Send `X-API-Key` on every request
- [ ] Send `X-User-Id` on mutations (POST, PATCH, DELETE)
- [ ] Parse the `Envelope` structure (`data`, `meta`, `errors`)
- [ ] Handle HTTP 422 rule rejections gracefully
- [ ] Cache state and label lists (they rarely change)
- [ ] Resolve state names to UUIDs for user-facing interfaces
- [ ] Paginate list requests when needed
- [ ] Exit non-zero on errors (for scripting/automation)
