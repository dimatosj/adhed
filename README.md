# ADHED

Headless task management for agents and claws.

A self-hosted REST API for task management with a deterministic rules engine.
Built for AI agents, CLI tools, and chat-driven workflows. No UI — API only.

## Quick Start

### With Claude Code (recommended)

```bash
git clone https://github.com/dimatosj/adhed.git
cd adhed
claude
```

### Without Claude Code

```bash
git clone https://github.com/dimatosj/adhed.git
cd adhed
./setup.sh
```

## Features

- **Issues** with subtasks, labels, projects, priorities, due dates, estimates
- **Fixed state machine**: triage → backlog → todo → in progress → done → canceled
- **Configurable rules engine** — trigger → condition → action, evaluated server-side
- **Full-text search** on titles and descriptions
- **Batch operations** — create and update multiple issues at once
- **Audit trail** on every mutation (who, what, when, diff)
- **Summary dashboard** — triage count, overdue, due soon, stalled projects
- **Multi-user, multi-team** with API key authentication

## API

Interactive docs at `http://localhost:8100/docs` after setup.

See [docs/api-reference.md](docs/api-reference.md) for the full reference.

## Rules Engine

Auto-label issues, enforce WIP limits, require fields before state changes, send notifications.

See [docs/rules-engine.md](docs/rules-engine.md) for triggers, conditions, actions, and examples.

## Integrations

- **NanoClaw / OpenClaw** — see [integrations/nanoclaw/](integrations/nanoclaw/)
- **Any HTTP client** — it's a REST API with JSON in/out

## Documentation

- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api-reference.md)
- [State Machine](docs/state-machine.md)
- [Rules Engine](docs/rules-engine.md)
- [Integration Guide](docs/integration-guide.md)

## License

MIT
