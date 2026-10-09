#!/usr/bin/env bash
# Pull latest main and rebuild. Run on the server.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
cd deploy
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker image prune -f
docker compose -f docker-compose.prod.yml ps
