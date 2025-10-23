# Docker Quickstart (public images)

Run the whole stack (API, Web, Ollama) using **published Docker images** — no local toolchain needed.

---

## 0) One-time setup

Create a small compose env file so the image names resolve:

```bash
    # .env.compose (at repo root)
    OWNER=ovanesb
    REPO=drupal-devops-copilot
    TAG=latest
```

## 1) Start everything

```bash
    COMPOSE_PROFILES=with-ollama \
    docker compose --env-file .env.compose \
      -f docker-compose.yml -f docker-compose.images.yml \
      up -d --pull always
```
* `COMPOSE_PROFILES=with-ollama` brings up the local Ollama service.
* Omit the profile if you use `OpenAI` (or another `LLM`) instead of `Ollama`.

## 2) Sanity checks

```bash
    # API healthy?
    curl http://localhost:8000/health
    
    # Ollama responding?
    curl http://localhost:11434/api/tags
```
If Ollama shows no models, pull our default model once:

```bash
    docker compose exec ollama ollama pull qwen2.5-coder:7b-instruct-q4_0
```
Open the UI: http://localhost:3000

## 3) Minimal configuration (env vars)

Create a `.env` from `.env.example` (or export in your shell) <br />
`.env.example` contains full list of variables:

> The compose file already passes OLLAMA_BASE_URL=http://ollama:11434 to the API.


## 4) Useful commands

```bash
    # Tail logs
    docker compose logs -f api
    docker compose logs -f web
    docker compose logs -f ollama
    
    # Exec into a service
    docker compose exec api sh
    docker compose exec web sh
    
    # Stop & remove
    docker compose down
```

## 5) Troubleshooting

* Port already allocated (`8000/3000/11434`): stop conflicting processes or change published ports in `docker-compose.yml`.
* Ollama shows no models: pull one as shown above, then retry.
* See also [docs/ollama-tips.md](docs/ollama-tips.md) for Ollama-specific troubleshooting.