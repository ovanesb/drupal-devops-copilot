#!/usr/bin/env bash
set -euo pipefail

: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8000}"
: "${ALEMBIC_CONFIG:=/app/server/alembic.ini}"

echo "[Co-Pilot API] Starting (host=${UVICORN_HOST} port=${UVICORN_PORT})"
echo "[Co-Pilot API] Working dir: $(pwd)"
echo "[Co-Pilot API] Python: $(python --version)"
echo "[Co-Pilot API] ALEMBIC_CONFIG=${ALEMBIC_CONFIG}"

# --- Verify alembic.ini exists ---
if [ ! -f "${ALEMBIC_CONFIG}" ]; then
  echo "[Co-Pilot API][ERROR] alembic.ini not found at ${ALEMBIC_CONFIG}"
  echo "[Co-Pilot API] Contents of /app/server:"
  ls -la /app/server || true
  exit 1
fi

# --- Run DB migrations (retry while DB becomes healthy) ---
echo "[Co-Pilot API] Running alembic upgrade head…"
attempt=0
until alembic upgrade head; do
  attempt=$((attempt+1))
  if [ $attempt -ge 12 ]; then
    echo "[Co-Pilot API][ERROR] Alembic failed after ${attempt} attempts."
    exit 1
  fi
  echo "[Co-Pilot API] Alembic failed (attempt ${attempt}), retrying in 5s…"
  sleep 5
done
echo "[Co-Pilot API] Alembic OK."

echo "[Co-Pilot API] Searching for app module…"
CANDIDATES=(
  "server.app:app"
  "server.main:app"
  "api.main:app"
  "app.main:app"
  "main:app"
)

FOUND_TARGET=""
for target in "${CANDIDATES[@]}"; do
  if python - <<PY
import importlib, sys
mod, var = "${target}".split(":")
try:
    m = importlib.import_module(mod)
    ok = hasattr(m, var)
    sys.exit(0 if ok else 2)
except Exception:
    sys.exit(2)
PY
  then
    FOUND_TARGET="${target}"
    echo "[Co-Pilot API] Found ${target}"
    break
  fi
done

if [ -z "${FOUND_TARGET}" ]; then
  echo "[Co-Pilot API][ERROR] Could not locate a FastAPI app. Checked:"
  for t in "${CANDIDATES[@]}"; do echo " - ${t}"; done
  echo "Hint: ensure one of those modules defines:  app = FastAPI(...)"
  ls -la /app/server || true
  exit 1
fi

echo "[Co-Pilot API] Launching Uvicorn: ${FOUND_TARGET}"
exec python -m uvicorn "${FOUND_TARGET}" --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" --proxy-headers --log-level info
