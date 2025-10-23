#!/usr/bin/env bash
set -euo pipefail

: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8000}"

echo "[Co-Pilot API] Starting FastAPI (host=${UVICORN_HOST} port=${UVICORN_PORT})"
echo "[Co-Pilot API] Searching for app module..."

CANDIDATES=(
  "server.app:app"
  "server.main:app"
  "api.main:app"
  "app.main:app"
  "main:app"
)

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
    echo "[Co-Pilot API] Found ${target}"
    exec python -m uvicorn "${target}" --host "$UVICORN_HOST" --port "$UVICORN_PORT" --proxy-headers
  fi
done

echo "Could not locate a FastAPI app. Checked:"
for t in "${CANDIDATES[@]}"; do echo " - ${t}"; done
echo "Hint: ensure one of those modules defines:  app = FastAPI(...)"
ls -la /app/server || true
exit 1
