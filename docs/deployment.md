# Deployment

ADHED is meant to be self-hosted. This guide covers running it
somewhere other than a laptop — TLS, reverse proxy, environment
config, and ops hardening.

## The short version

Put ADHED behind a reverse proxy (Caddy, nginx, Traefik) that
terminates TLS. Don't expose the uvicorn port or the Postgres port
to the public internet. Rotate the API key anytime it leaves trusted
hands (currently "rotate" means re-run `/setup` on a fresh DB —
see [post-launch work in SECURITY.md](../SECURITY.md#known-post-launch-work)).

## Environment variables

| Name | Default | Purpose |
|------|---------|---------|
| `DATABASE_URL` | *(required)* | Async Postgres URL, e.g. `postgresql+asyncpg://adhed:adhed@localhost:5432/adhed` |
| `DATABASE_URL_SYNC` | *(unused)* | Reserved for migration-only sync drivers |
| `API_PORT` | `8100` | Port uvicorn binds |
| `DB_PORT` | `5433` | Host port compose exposes Postgres on |
| `DB_BIND` | `127.0.0.1` | Host interface for the exposed DB port. Set to `0.0.0.0` only if you need off-host DB access. |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warning` / `error` |
| `LOG_FORMAT` | `plain` | `plain` for human output, `json` for log-aggregation pipelines |

Copy `.env.example` to `.env` and set what you need — compose reads
it automatically.

## TLS + reverse proxy

### Caddy (recommended)

Easiest option. One block, automatic Let's Encrypt:

```caddy
adhed.example.com {
    reverse_proxy localhost:8100
}
```

Run `caddy run` with this as your `Caddyfile`. Done.

### nginx

```nginx
server {
    listen 443 ssl http2;
    server_name adhed.example.com;

    ssl_certificate     /etc/letsencrypt/live/adhed.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/adhed.example.com/privkey.pem;

    # Security headers. Adjust CSP if you serve the Swagger UI.
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options     "nosniff" always;
    add_header Referrer-Policy            "strict-origin-when-cross-origin" always;

    # Rate limit unauthed + bursty endpoints.
    # Apply to /api/v1/setup and the auth failure surface especially.
    limit_req_zone $binary_remote_addr zone=adhed_rl:10m rate=10r/s;
    limit_req     zone=adhed_rl burst=20 nodelay;

    # Upload cap — ADHED doesn't serve binary uploads but bad clients
    # can still try. custom_fields JSONB has no enforced size limit.
    client_max_body_size 1m;

    location / {
        proxy_pass         http://127.0.0.1:8100;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
}
```

## Running with docker compose

```bash
docker compose up -d
docker compose logs -f adhed-api
```

The API container auto-runs `alembic upgrade head` on startup.
Safe to re-run — migrations are idempotent.

## Running without docker compose

For environments where Postgres is managed elsewhere (RDS, managed
Postgres, an existing cluster):

```bash
pip install -r requirements.lock         # reproducible deps
alembic upgrade head
uvicorn taskstore.main:app \
    --host 127.0.0.1 --port 8100 \
    --workers 2 \
    --proxy-headers \
    --forwarded-allow-ips="*"             # trust X-Forwarded-For from the proxy
```

Put it behind systemd, supervisord, or similar for auto-restart.

## Hardening checklist

- [ ] TLS terminated at reverse proxy (never run uvicorn on
      the public internet)
- [ ] Reverse proxy rate-limits requests — especially `/api/v1/setup`
      and any path that returns 401
- [ ] `DB_BIND=127.0.0.1` (default) or Postgres isn't exposed to
      the host at all
- [ ] DB credentials changed from compose defaults (`adhed`/`adhed`)
      for any production-like deployment
- [ ] `.adhed-credentials` file is readable only by the deployer
      (contains the plaintext API key)
- [ ] `LOG_FORMAT=json` in production so logs are ingestible
- [ ] Regular Postgres backups (ADHED does not manage its own)
- [ ] Restart the API and DB containers on reboot
      (`restart: unless-stopped` is set in compose)

## Monitoring

- Liveness: `GET /api/v1/health` returns `200` with `{"status":"ok"}`
  when the DB is reachable, `503` otherwise.
- No metrics endpoint yet — watch the reverse proxy's request logs
  and the container's structured logs.

## Upgrades

```bash
git pull
docker compose build adhed-api
docker compose up -d adhed-api            # recreates the container
```

Migrations run on container start. Check the container logs for
`Running upgrade ... -> ...` lines.

Rollback: `git checkout <previous-tag>` and redeploy. Note that
alembic *forward* migrations are well tested; downgrades are not.
For production, take a DB snapshot before upgrading to a release
whose migrations touch existing tables.

## Logs to keep an eye on

Events worth alerting on:

- `auth_invalid_api_key` (repeated) — key leak or brute-force attempt
- `rule_evaluation_error_surfaced` — a team's rule is broken
- `set_field_blocked` — a rule tried to write a forbidden field;
  almost always an operator or client bug, but worth investigating
- Any `ERROR` level log — uncaught exceptions bubble up here

With `LOG_FORMAT=json`, each of these emits a structured record
with `rule_id`, `rule_name`, `client_ip`, or `path` in the
top-level keys.
