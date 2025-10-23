# docker/api.Dockerfile
FROM python:3.11-slim

WORKDIR /app

# --- System dependencies ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    git openssh-client curl build-essential && \
    rm -rf /var/lib/apt/lists/*

# --- Copy manifests if they exist ---
# We copy them separately and ignore if missing
# (Docker only errors if a file listed in COPY does not exist)
# So we add them conditionally
COPY pyproject.toml /app/pyproject.toml
COPY requirements.txt /app/requirements.txt

# --- Install dependencies ---
RUN if [ -f "requirements.txt" ]; then pip install --no-cache-dir -r requirements.txt; fi
RUN if [ -f "pyproject.toml" ]; then pip install --no-cache-dir . || true; fi

# --- Copy project source ---
COPY copilot/ ./copilot/
COPY server/ ./server/
COPY docker/entrypoint.api.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
