FROM python:3.12-slim

# Run as non-root. Deps are installed as root, then we drop privileges
# before serving. The runtime user owns nothing writable on disk.
RUN useradd --create-home --uid 1000 adhed

WORKDIR /app

# Layer 1: pinned deps — changes rarely. Cached across code edits so
# the expensive install step is skipped when only app code changes.
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && \
    pip install --no-cache-dir psycopg2-binary

# Layer 2: package metadata — changes occasionally.
COPY pyproject.toml .

# Layer 3: application code — changes on every commit. Installed with
# --no-deps since everything in pyproject.toml is already in the lock.
COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/
RUN pip install --no-cache-dir --no-deps -e .

ENV PYTHONPATH=/app/src

USER adhed

CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn taskstore.main:app --host 0.0.0.0 --port ${API_PORT:-8100}"]
