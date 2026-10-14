#!/usr/bin/env bash
# Start backend (FastAPI :8000) and frontend (Next.js :3000) for local development.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACK=$!
trap 'kill $BACK 2>/dev/null || true' EXIT
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then npm install; fi
npm run dev
