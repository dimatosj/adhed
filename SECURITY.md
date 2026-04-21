# Security Policy

## Reporting a vulnerability

**Please do not open a public GitHub issue for security reports.**

Email `security@brindilletwig.com` with a description of the issue,
reproduction steps, and any relevant logs or commands. We'll
acknowledge within 3 business days and aim to triage within 7.

If you prefer, you can also use GitHub's private vulnerability
reporting: go to the Security tab → "Report a vulnerability".

## Scope

In scope:
- Authentication / authorization bypass
- Cross-tenant data access
- SQL injection, template injection, or command execution
- Denial-of-service via crafted API inputs
- Sensitive data exposure (API keys, audit trails, PII)

Out of scope:
- Attacks requiring physical access or a compromised host
- Denial-of-service via raw request volume (rate limiting is a
  reverse-proxy concern — see [docs/deployment.md](docs/deployment.md))
- Social-engineering the project maintainers

## Threat model

ADHED assumes:
- **API keys are secrets.** Anyone holding a team's API key can read,
  write, and delete that team's data at the role level their
  membership grants. Rotate by regenerating the team (no key-
  rotation endpoint yet).
- **X-User-Id is declared, not authenticated.** Team members share
  the team's API key; the X-User-Id header identifies which member
  is acting. A holder of the API key can set any valid member's ID.
  Audit entries record the declared user — they are non-repudiable
  only at the team level, not the individual level.
- **Rules engine is trusted input.** Team members who can create
  rules (OWNER + ADMIN) can author logic that runs on every write
  in that team. The `set_field` action is whitelisted to prevent
  cross-tenant moves and audit forgery, but ADMIN access is still
  powerful. Audit every rule change.
- **Postgres is trusted.** Direct DB access bypasses every check
  in this codebase.

## Hardening guidance

See [docs/deployment.md](docs/deployment.md) for running ADHED
beyond localhost (TLS termination, reverse-proxy rate limiting,
network isolation, log aggregation).

## Known post-launch work

These are tracked but not yet fixed:

- API keys are not rotatable via the API (regenerate = recreate team).
- No per-team rate limiting (depend on reverse proxy).
- Audit entries have no retention policy (grow unbounded).
- Role-change endpoint doesn't exist; role elevation requires direct
  DB access.

If you're relying on ADHED for anything important, read this list
and mitigate as appropriate at the infrastructure layer.
