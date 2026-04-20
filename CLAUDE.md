# ADHED — headless task management for agents and claws

## Setup (First Time)

If `.adhed-credentials` does not exist, the user needs setup. Walk them through it:

1. Verify Docker: `docker info`. If failing, try `open -a Docker` (macOS) or explain how to start it.
2. Check port 8100: `lsof -i :8100`. If occupied, ask user to choose another and set API_PORT in .env.
3. Check port 5433: `lsof -i :5433`. If occupied, ask user to choose another and set DB_PORT in .env.
4. Start services: `docker compose up -d`
5. Wait for healthy: `for i in $(seq 1 30); do curl -sf http://localhost:${API_PORT:-8100}/api/v1/health >/dev/null 2>&1 && break; sleep 2; done`
6. Ask the user for: name, email, team name (default "Home")
7. Derive team key from team name (uppercase, letters only, first 10 chars)
8. Create team: `curl -sf -X POST http://localhost:${API_PORT:-8100}/api/v1/setup -H "Content-Type: application/json" -d '{"team_name":"...","team_key":"...","user_name":"...","user_email":"..."}'`
9. Save response to `.adhed-credentials` in the format:
   ```
   API_KEY=adhed_...
   USER_ID=...
   TEAM_ID=...
   URL=http://localhost:8100
   ```
10. Tell the user their credentials and explain next steps:
    - API docs at http://localhost:8100/docs
    - Read docs/getting-started.md for first steps
    - Try: `source .adhed-credentials && curl -s http://localhost:8100/api/v1/teams/$TEAM_ID/issues -H "X-API-Key: $API_KEY" | python3 -m json.tool`

If setup fails at any step, diagnose and fix — don't tell the user to figure it out.

## Already Set Up

If `.adhed-credentials` exists, ADHED is configured. Help the user with whatever they need:

- API is at http://localhost:${API_PORT:-8100}
- Interactive API docs at http://localhost:${API_PORT:-8100}/docs
- Credentials in `.adhed-credentials`
- To check services: `docker compose ps`
- To restart: `docker compose restart`
- To view logs: `docker compose logs -f adhed-api`

## NanoClaw / OpenClaw Integration

If user asks about NanoClaw or OpenClaw integration:

1. Ask where their project is (or search ~/projects/ for nanoclaw/ziggyclaw/openclaw directories)
2. Copy `integrations/nanoclaw/life/` to their `container/skills/life/`
3. Source `.adhed-credentials` and add env vars to their NanoClaw `.env`:
   ```
   TASKSTORE_URL=http://host.docker.internal:8100
   TASKSTORE_API_KEY=<from .adhed-credentials>
   TASKSTORE_USER_ID=<from .adhed-credentials>
   TASKSTORE_TEAM_ID=<from .adhed-credentials>
   ```
4. Check if their `src/container-runner.ts` passes TASKSTORE env vars to containers. If not, explain they need the ADHED skill branch or upstream env passthrough (see qwibitai/nanoclaw#1867).
5. Rebuild: `cd <their-project> && npm run build`
6. Restart their service
7. Suggest creating a dedicated Tasks room in their messaging channel

## Development

### Prerequisites
- Python 3.12+
- Docker + Docker Compose

### Local dev (without Docker for the API)

```bash
docker compose up -d adhed-db      # Start just Postgres
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn taskstore.main:app --port 8100 --reload
```

### Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

Tests require a Postgres instance with an `adhed_test` database.

### Key files

| File | Purpose |
|------|---------|
| `src/taskstore/main.py` | FastAPI app, router wiring |
| `src/taskstore/api/` | REST endpoint routers |
| `src/taskstore/services/` | Business logic layer |
| `src/taskstore/engine/` | Core engine (transitions, audit, defaults) |
| `src/taskstore/rules/` | Rules engine (conditions, actions, evaluator) |
| `src/taskstore/models/` | SQLAlchemy ORM models |
| `src/taskstore/schemas/` | Pydantic request/response schemas |
| `docker-compose.yml` | API + Postgres containers |
| `alembic/` | Database migrations |

### Architecture

Three layers:
1. **Core Engine** (immutable) — state machine transitions, audit trail, default state seeding, subtask integrity
2. **Rules Engine** (configurable) — trigger → condition → action rules, evaluated on every write operation
3. **REST API** — FastAPI endpoints consumed by any HTTP client
