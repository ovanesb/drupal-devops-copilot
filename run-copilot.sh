#!/usr/bin/env bash
set -euo pipefail

OWNER="ovanesb"
REPO="drupal-devops-copilot"
TAG="latest"

# Clean old
docker rm -f web api ollama 2>/dev/null || true
docker network rm copilotnet 2>/dev/null || true

# Network
docker network create copilotnet || true

# Ollama (no host port publish)
docker run -d --name ollama --network copilotnet \
  ollama/ollama:latest

# Wait for Ollama (no curl required)
until docker exec ollama ollama list >/dev/null 2>&1; do
  sleep 2
done

# Pull model (one-time per host)
docker exec ollama ollama pull qwen2.5-coder:7b-instruct-q4_0

# API
docker run -d --name api --network copilotnet \
  -p 8000:8000 \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  ghcr.io/${OWNER}/${REPO}-api:${TAG}

# Wait for API
until curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; do sleep 2; done
curl -fsS http://127.0.0.1:8000/health && echo

# Web
docker run -d --name web --network copilotnet \
  -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
  ghcr.io/${OWNER}/${REPO}-web:${TAG}

echo "Open http://localhost:3000"

