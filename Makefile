.PHONY: up up-no-ollama down logs api web cli build

up:
	COMPOSE_PROFILES=with-ollama docker compose up -d --build

up-no-ollama:
	COMPOSE_PROFILES=without-ollama docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

api:
	open http://localhost:8000/docs || true

web:
	open http://localhost:3000 || true

cli:
	docker compose run --rm cli "copilot-workflow --help"

auto-dev:
	docker compose run --rm cli "copilot-auto-dev CCS-18 --base main --execute --no-draft"
