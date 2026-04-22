# Fragments

Fragments are typed notes — structured pieces of context that don't belong in an issue but that agents need to remember. A plumber's phone number, a WiFi password, an idea for the kitchen renovation, a journal entry about how the week went.

Every fragment has a type, optional topics and domains, and full-text search across all of it.

## Fragment Types

| Type | What it's for | Example |
|------|--------------|---------|
| `person` | People, contacts, service providers | "Tony at Ace Plumbing — reliable, does weekends" |
| `place` | Locations, venues, addresses | "Dr. Kim's office is at 340 Oak St, parking in back" |
| `credential` | Passwords, access codes, tokens | "WiFi: butterfly_orange" |
| `memory` | Facts, decisions, context to remember | "We decided to go with quartz countertops, not granite" |
| `idea` | Ideas, brainstorms, things to explore | "What if we added a skylight to the kitchen?" |
| `resource` | Links, documents, references | "Tile inspiration board: pinterest.com/..." |
| `journal` | Logs, reflections, daily notes | "Good day — finished the triage backlog, gym, early bed" |

## Create a Fragment

```bash
source .adhed-credentials
curl -s -X POST "$URL/api/v1/teams/$TEAM_ID/fragments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{
    "text": "Tony from Ace Plumbing was great — showed up on time, fixed the leak, $150",
    "type": "person",
    "summary": "Tony at Ace Plumbing, reliable plumber",
    "topics": ["contractors", "home-maintenance"],
    "domains": ["home"],
    "entities": [{"name": "Tony", "type": "person", "role": "plumber", "org": "Ace Plumbing"}],
    "source": {"room": "General"}
  }'
```

## Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `text` | string | yes | Main content |
| `type` | string | yes | One of the seven types above |
| `summary` | string | no | Short description (included in full-text search) |
| `topics` | string[] | no | Up to 3 topic tags |
| `domains` | string[] | no | Domain tags (e.g. "home", "health", "work") |
| `entities` | object[] | no | Extracted entities (people, orgs, etc.) |
| `source` | object | no | Where this came from (see below) |

### Source metadata

| Field | Type | Notes |
|-------|------|-------|
| `room` | string | Chat room or channel name |
| `linked_project_id` | string | Associated project |
| `linked_issue_id` | string | Associated issue |
| `conversation_timestamp` | string | When the info was captured |
| `unresolved_reference` | string | Cross-reference to resolve later |

## List and Filter

```bash
# All fragments
curl -s "$URL/api/v1/teams/$TEAM_ID/fragments" \
  -H "X-API-Key: $API_KEY"

# Only people
curl -s "$URL/api/v1/teams/$TEAM_ID/fragments?type=person" \
  -H "X-API-Key: $API_KEY"

# Multiple types
curl -s "$URL/api/v1/teams/$TEAM_ID/fragments?type=person,credential" \
  -H "X-API-Key: $API_KEY"

# By domain
curl -s "$URL/api/v1/teams/$TEAM_ID/fragments?domain=health" \
  -H "X-API-Key: $API_KEY"

# By topic
curl -s "$URL/api/v1/teams/$TEAM_ID/fragments?topic=contractors" \
  -H "X-API-Key: $API_KEY"

# Full-text search
curl -s "$URL/api/v1/teams/$TEAM_ID/fragments?title_search=plumbing" \
  -H "X-API-Key: $API_KEY"

# Linked to a project
curl -s "$URL/api/v1/teams/$TEAM_ID/fragments?project_id=$PROJECT_ID" \
  -H "X-API-Key: $API_KEY"
```

### Filter parameters

| Parameter | Type | Notes |
|-----------|------|-------|
| `type` | string | Comma-separated fragment types |
| `domain` | string | Comma-separated domains |
| `topic` | string | Single topic |
| `project_id` | string | Fragments linked to a project |
| `issue_id` | string | Fragments linked to an issue |
| `entity_name` | string | Search within entities |
| `title_search` | string | Full-text search on text + summary |
| `created_by` | UUID | Filter by author |
| `limit` | int | Max results (default 50, max 200) |
| `offset` | int | Pagination offset |
| `sort` | string | `created_at`, `updated_at`, or `type` |
| `order` | string | `asc` or `desc` (default `desc`) |

## Topic Aggregation

See which topics have the most fragments:

```bash
curl -s "$URL/api/v1/teams/$TEAM_ID/fragments/topics" \
  -H "X-API-Key: $API_KEY"
```

```json
{
  "data": [
    {"topic": "contractors", "count": 5},
    {"topic": "home-maintenance", "count": 3},
    {"topic": "health", "count": 2}
  ]
}
```

## Update a Fragment

```bash
curl -s -X PATCH "$URL/api/v1/fragments/$FRAGMENT_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID" \
  -d '{"topics": ["contractors", "plumbing"], "summary": "Tony — Ace Plumbing, reliable, $150/visit"}'
```

## Delete a Fragment

```bash
curl -s -X DELETE "$URL/api/v1/fragments/$FRAGMENT_ID" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID"
```

Returns 204 with no body.

## Audit

All fragment operations (create, update, delete) are recorded in the audit trail:

```bash
curl -s "$URL/api/v1/teams/$TEAM_ID/audit?entity_type=fragment" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-Id: $USER_ID"
```

## How Agents Use Fragments

Fragments give agents a place to store context that isn't a task. When a user mentions their dentist's name in a chat, the agent creates a `person` fragment. When they share a WiFi password, it's a `credential`. When they say "let's go with the blue tiles," it's a `memory` linked to the kitchen project.

Later, when the agent needs that context — "who was that plumber?" or "what did we decide about the countertops?" — it queries fragments by type, topic, or full-text search instead of scrolling through conversation history.

The `source` field tracks provenance: which chat room, which conversation, which project or issue the fragment relates to. This lets agents connect notes back to the context they came from.
