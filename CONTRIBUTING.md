# Contributing to ADHED

Thanks for your interest. ADHED is a small, focused project — we favour
clarity and explicitness over flexibility. This document exists to save
you time on a first PR.

## What's in scope

- Fixes: bugs, security issues, incorrect documentation.
- Rules engine additions (new condition types, action types).
- New query filters / sort orders on list endpoints.
- Performance work (especially N+1 fixes).
- Tests for existing untested paths.

## What's explicitly out of scope

- **A UI.** ADHED is headless by design. Chat agents, CLIs, and custom
  frontends are the expected callers.
- **Multi-DB support.** Postgres is the only target. We rely on JSONB,
  TSVECTOR, GIN indexes, and `pgcrypto` — all Postgres features.
- **Hosted / SaaS features** (billing, organizations-of-teams, sharding).
  ADHED is self-hosted.
- **Non-English full-text search.** `to_tsvector('english', ...)` is
  hard-coded in the migration; open an issue to discuss if you need
  another language.

## Before you open a PR

1. Read the relevant doc:
   - [Architecture](docs/architecture.md) — 3-layer design
   - [API Reference](docs/api-reference.md) — endpoint shapes
   - [Rules Engine](docs/rules-engine.md) — conditions & actions
   - [State Machine](docs/state-machine.md) — transitions
2. Look for an existing issue. If one exists, comment that you're working
   on it. If not, open one describing the problem before writing code —
   we'll save you time on direction.
3. For security issues, see [SECURITY.md](SECURITY.md) — please do NOT
   open a public issue.

## Development setup

```bash
git clone https://github.com/dimatosj/adhed.git
cd adhed
docker compose up -d adhed-db          # Just the DB
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn taskstore.main:app --port 8100 --reload
```

Run tests:

```bash
pytest tests/ -v
```

Tests require a Postgres reachable at `localhost:5433` with user
`adhed`, password `adhed`, and database `adhed_test`. If you ran
`./setup.sh`, the test database was created automatically. Otherwise:

```bash
docker compose up -d adhed-db
docker exec $(docker compose ps -q adhed-db) psql -U adhed -c "CREATE DATABASE adhed_test;"
```

Install pre-commit (optional but avoids CI round-trips):

```bash
pre-commit install
```

## Pull request checklist

- [ ] Tests pass: `pytest tests/`
- [ ] Lint passes: `ruff check src/ tests/`
- [ ] Format clean: `ruff format --check src/ tests/`
- [ ] New features have tests
- [ ] Bug fixes have regression tests
- [ ] Documentation updated if behaviour changed
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`

## Style

- **Comments**: default to none. Only add one when the *why* is non-
  obvious — a hidden constraint, a subtle invariant, a workaround for
  a specific bug. Don't restate what the code does.
- **Tests**: one behaviour per test. Test name describes the behaviour,
  not the mechanism.
- **Error messages**: client-facing messages must not leak internal
  enum paths, table names, or sensitive identifiers. Log the detail
  server-side; give the client a clean message.
- **Commits**: short imperative-mood summary (`add X`, `fix Y`). Body
  explains the *why* when it matters.

## Running a specific test

```bash
pytest tests/test_roles.py::test_member_cannot_delete_label -xvs
```

The `-xvs` trio (exit-on-first-fail, verbose, show prints) is what
most of the project's tests are debugged with.

## Asking for help

Open a GitHub Discussion or a draft PR — both are welcome.
