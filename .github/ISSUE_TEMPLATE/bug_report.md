---
name: Bug report
about: Something's broken
labels: bug
---

## What happened

<!-- The actual behaviour. Include exact HTTP status codes,
     response bodies, and any errors from the server log. -->

## What you expected

<!-- The behaviour you thought you'd get. -->

## Steps to reproduce

<!-- Ideally a curl command or Python snippet. If the rules
     engine is involved, include the rule JSON. -->

```bash
curl ...
```

## Environment

- ADHED version / commit:
- Python version:
- Postgres version:
- Running via: `docker compose` / `uvicorn` / other

## Relevant logs

<!-- Paste the server output around the failure. If auth-related,
     include the response headers (redact the API key). -->
