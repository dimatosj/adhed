# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0] — Pre-launch hardening

First public-ready release.

### Added
- **Role-based access control** (OWNER / ADMIN / MEMBER) enforced
  across every endpoint; see [API Reference](docs/api-reference.md).
  MEMBER callers automatically see only their own audit entries.
- **Audit trail** for every mutation: issues, comments, rules,
  labels, projects, teams, and memberships.
- **Uniform response envelope** — every response (success or error)
  has the same `{"data", "meta", "errors", "warnings"}` shape.
- **Structured logging** with `LOG_FORMAT=json` option for log
  aggregation pipelines (Loki, Datadog, CloudWatch).
- **Health endpoint** runs `SELECT 1` against the DB; returns 503
  on failure so orchestrators can drain traffic.
- **Cross-tenant reference validation** on every Issue write —
  `state_id`, `project_id`, `parent_id`, `label_ids`, and
  `assignee_id` must all belong to the authed team.
- **`count_query` rule conditions** exclude archived issues by
  default (opt in via `include_archived: true`).
- CI workflow, lockfile, pre-commit config, CONTRIBUTING, SECURITY.
- [Deployment guide](docs/deployment.md) covering TLS and
  reverse-proxy hardening.
- [Architecture doc](docs/architecture.md) describing the three-
  layer design.

### Security
- **SHA-256 hashed API keys** — stored as hashes, returned in
  plaintext exactly once at creation. `GET /teams/{id}` no longer
  echoes the key.
- **`POST /teams` requires an OWNER caller.** `/setup` remains the
  only unauthenticated bootstrap path.
- **`UserCreate` no longer accepts a `role` field** — roles are
  assigned server-side based on membership order.
- **`set_field` rule action whitelisted** to `priority`, `estimate`,
  `assignee_id`, `project_id`, `due_date`, `state_id` — rejects
  dangerous fields (`team_id`, `created_by`, `id`, `archived_at`)
  at rule-creation and -application time.
- **Rule evaluator fails loudly** on malformed rules (previously
  silently skipped, which broke WIP-limit enforcement).
- **Non-root Dockerfile** — API runs as UID 1000.
- **Postgres bound to loopback by default** (override with `DB_BIND`
  in `.env`).

### Changed
- State-transition errors no longer leak Python enum paths
  (`StateType.TRIAGE`) — use clean value strings.
- Missing `X-API-Key` returns 401 (was FastAPI's default 422).
- `POST /teams` auto-adds the creator as OWNER of the new team.
- Default labels in `/setup` are opt-in via `include_default_labels`.

### Infrastructure
- GitHub Actions CI runs pytest, ruff check/format, and pip-audit.
- Lockfile (`requirements.lock`) for reproducible installs.
- Pre-commit config with ruff format/check, trailing-whitespace,
  EOL, YAML/TOML syntax, large-file detection, merge-conflict
  markers.
