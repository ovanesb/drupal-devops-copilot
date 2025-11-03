# docker/api.Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# --- System deps (curl for healthcheck; build tools only if needed) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Copy manifests if they exist ---
COPY requirements.txt /app/requirements.txt
COPY pyproject.toml /app/pyproject.toml

# --- Base runtime deps needed for Sprint 2 ---
# (Install first to allow caching when app code changes)
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    sqlalchemy \
    alembic \
    psycopg2-binary \
    pydantic

# --- Project deps (optional if you also have requirements/pyproject) ---
RUN if [ -f "requirements.txt" ]; then pip install --no-cache-dir -r requirements.txt; fi
RUN if [ -f "pyproject.toml" ]; then pip install --no-cache-dir . || true; fi

# --- Copy application source ---
# Must include server/ (FastAPI app + alembic.ini/env.py/versions)
# and your existing CLI helpers in copilot/ (if used by endpoints)
COPY server/ /app/server/
COPY copilot/ /app/copilot/

# --- Entrypoint ---
COPY docker/entrypoint.api.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
