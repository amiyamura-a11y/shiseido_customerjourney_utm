.PHONY: setup backend frontend dev test build

setup:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

frontend:
	cd frontend && npm run dev

dev:
	./scripts/dev.sh

test:
	cd backend && . .venv/bin/activate && python -m pytest -q

build:
	cd frontend && npm run build
