#!/usr/bin/env bash
# Production-style single process: FastAPI serves API + built frontend on :8000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
[ -f .env ] || cp .env.example .env
exec .venv/bin/uvicorn app.main:app --host "${LEARNPATH_HOST:-0.0.0.0}" --port "${LEARNPATH_PORT:-8000}"
