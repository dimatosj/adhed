# ADHED

**Headless task management for AI agents, CLIs, and chat-driven workflows.**

[![CI](https://github.com/dimatosj/adhed/actions/workflows/ci.yml/badge.svg)](https://github.com/dimatosj/adhed/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

ADHED is a self-hosted REST API for task management with a
deterministic, server-side rules engine. No UI — API only.
Designed for bots, agents, and scripts, not humans clicking buttons.

## Why this exists

Linear, Notion, Todoist, and friends are UI-first. Their APIs are
an afterthought — rate-limited, undocumented-in-places, and
frequently opinionated about what a "task" means.

ADHED flips the stack:

- **API-first.** Every feature is reachable over HTTP with
  `curl`. Interactive docs at `/docs`.
- **Rules run on the server.** You write a rule like *"reject new
  issues without a priority if more than 3 are already in
  progress"* once, and every agent / CLI / human writing through
  the API gets the enforcement for free.
- **Deterministic.** Same request → same behaviour. Broken rules
  fail loudly. Audit trail on every mutation.
- **Yours.** Self-hosted. Your data, your keys, your infra.

Built for the workflow where a chat agent is capturing tasks, a
classifier is labelling them, a CLI is triaging, and maybe a
human occasionally pokes the `/docs` page. The database is the
single source of truth they all agree on.

## 30-second demo

```bash
$ ./setup.sh
  Your name: Jane
  Your email: jane@example.com
  Team name [Home]: Home
  ✅ ADHED is running!
  API Key: adhed_a1b2c3...
  URL:     http://localhost:8100

$ source .adhed-credentials
$ curl -s -X POST "$URL/api/v1/teams/$TEAM_ID/issues" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -H "X-User-Id: $USER_ID" \
    -d '{"title":"Call the dentist","priority":2}' | jq .data.title
"Call the dentist"

$ curl -s "$URL/api/v1/teams/$TEAM_ID/summary" \
    -H "X-API-Key: $API_KEY" \
    -H "X-User-Id: $USER_ID" | jq .data.triage_count
1
```

## Quick start

### With Claude Code (recommended)

```bash
git clone https://github.com/dimatosj/adhed.git
cd adhed
claude
```

Claude walks through Docker setup, prompts for your name/email/team,
starts services, saves credentials, and points you at `/docs`.

### Without Claude Code

```bash
git clone https://github.com/dimatosj/adhed.git
cd adhed
./setup.sh
```

Requires Docker + curl. Everything else is handled.

## What's in the box

- **Issues** with subtasks, labels, projects, priorities, due
  dates, estimates, custom fields
- **Six-state workflow** (triage → backlog → todo → in progress →
  done → canceled) with enforced valid transitions
- **Rules engine** — trigger → condition → action, evaluated
  server-side on every write. Reject, auto-label, set fields,
  notify, add comments.
- **Full-text search** on titles and descriptions (Postgres TSVECTOR)
- **Batch operations** — create and update many issues at once
- **Audit trail** on every mutation across every entity
- **Summary dashboard** — triage count, overdue, due soon, stalled
  projects, waiting-for
- **Role-based access** (OWNER / ADMIN / MEMBER) with MEMBER audit
  self-filtering
- **Multi-team**, team-level API keys (SHA-256 hashed at rest)

## API

Interactive docs: `http://localhost:8100/docs` after setup.

See the full [API Reference](docs/api-reference.md).

## Rules Engine

Write a rule once, and it runs on every write. Examples:

- *"Auto-label any issue whose title contains 'dentist' or 'gym'
  with `health`."*
- *"Reject moving an issue from triage unless priority is set."*
- *"If more than 3 issues are in progress, reject creating another."*
- *"When an issue is assigned, notify the assignee."*

See [Rules Engine](docs/rules-engine.md) for the full DSL.

## Integrations

- **[NanoClaw / OpenClaw](integrations/nanoclaw/)** — drop-in
  skill for Claude-in-container workflows
- **Any HTTP client** — it's REST with JSON in / JSON out

## Documentation

- [Getting Started](docs/getting-started.md) — setup walkthrough
- [API Reference](docs/api-reference.md) — every endpoint, parameter, response
- [State Machine](docs/state-machine.md) — the six state categories
  and transitions
- [Rules Engine](docs/rules-engine.md) — conditions, actions, examples
- [Integration Guide](docs/integration-guide.md) — building clients
- [Architecture](docs/architecture.md) — the three-layer design
- [Deployment](docs/deployment.md) — running beyond localhost

## Contributing

Bug reports, security reports, and PRs welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
