
---

### `docs/docker-dev.md`

# Docker for Development (live-reload)

Containerized developer workflow with **source mounts** and **hot reload** (no global Python/Node toolchain required).

---

## 1) Start the dev stack (build from local source)

```bash
    COMPOSE_PROFILES=with-ollama docker compose up -d --build
```

This uses your local code:
* API mounts server/ and copilot/ into the container; uvicorn reloads on changes.
* Web mounts ui/ and uses Next.js dev server for fast refresh.
* Ollama runs locally in a container and is reachable by the API.

> If you don’t want Ollama, omit the profile and set `LLM_PROVIDER=openai` + `OPENAI_API_KEY` in `.env`.

## 2) First-time: pull a local model (Ollama)

If you’re using Ollama and no models are present:

```bash
  docker compose exec ollama ollama pull qwen2.5-coder:7b-instruct-q4_0
```

## 3) Verify

```bash
    # API
    curl http://localhost:8000/health
    
    # Ollama
    curl http://localhost:11434/api/tags
```
Open the UI: http://localhost:3000

## 4) Live-reload behavior

* Backend (FastAPI): edit files under server/ or copilot/ → auto-reload.
* Frontend (Next.js): edit ui/ → hot refresh in the browser.

No container restarts required for typical code changes.

## 5) Environment variables (developer defaults)
Create a `.env` from `.env.example` (or export in your shell) <br />
`.env.example` contains full list of variables:

## 6) Day-to-day commands

```bash
    # Build & start
    COMPOSE_PROFILES=with-ollama docker compose up -d --build
    
    # Tail logs
    docker compose logs -f api
    docker compose logs -f web
    docker compose logs -f ollama
    
    # Exec for debugging
    docker compose exec api sh
    docker compose exec web sh
    
    # Stop / remove
    docker compose down
```

## 7) Common issues

* Ports busy: `8000 (API)`, `3000 (Web)`, `11434 (Ollama)`. Stop other services or adjust published ports in `docker-compose.yml`.
* File changes not detected (Mac/Windows): ensure the volumes are mounted (they are by default). If edits aren’t detected, try `docker compose restart api web`.
* Performance tuning: consider allocating more RAM/CPU to Docker Desktop when running large models with Ollama.