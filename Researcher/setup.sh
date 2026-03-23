#!/usr/bin/env bash
# Vera Research Agent — quick setup
set -euo pipefail

echo "=== Vera Research Agent Setup ==="

# 1. Python deps
echo ""
echo "→ Installing Python dependencies…"
pip install -r requirements.txt

# 2. PostgreSQL via Docker Compose
echo ""
echo "→ Starting PostgreSQL (Docker)…"
docker compose up -d postgres

echo "  Waiting for PostgreSQL to be ready…"
until docker compose exec -T postgres pg_isready -U vera -d vera_research &>/dev/null; do
  printf "."
  sleep 1
done
echo " ready!"

# 3. Set env var
echo ""
echo "→ Setting VERA_DB_URL…"
export VERA_DB_URL="postgresql://vera:vera_secret@localhost:5432/vera_research"

echo ""
echo "=== Setup complete ==="
echo ""
echo "  To start the API:"
echo "    export VERA_DB_URL=postgresql://vera:vera_secret@localhost:5432/vera_research"
echo "    python researcher_api.py"
echo ""
echo "  Open frontend/index.html in your browser."
echo ""
echo "  For pgAdmin:  docker compose --profile admin up -d pgadmin"
echo "    then visit  http://localhost:5050"
echo "    login:      admin@vera.local / admin"
echo ""