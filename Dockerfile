FROM python:3.12-slim

# Run as non-root. Deps are installed as root, then we drop privileges
# before serving. The runtime user owns nothing writable on disk.
RUN useradd --create-home --uid 1000 adhed

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir . && pip install --no-cache-dir psycopg2-binary

COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/

ENV PYTHONPATH=/app/src

USER adhed

CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn taskstore.main:app --host 0.0.0.0 --port ${API_PORT:-8100}"]
