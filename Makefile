.PHONY: up down logs test ingest backfill backfill-history migrate fmt

# --- Docker stack ---
up:            ## build + run the full stack (db, api, worker, frontend)
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

# --- Backend (inside the api container) ---
migrate:       ## apply DB migrations
	docker compose exec api alembic upgrade head

# Ingest one filer's recent filings:  make ingest CIK=0001067983 FORMS=13F-HR
ingest:
	docker compose exec api python -m app.cli ingest-filer $(CIK) --forms $(or $(FORMS),13F-HR)

# Backfill recent days from the daily index: make backfill FORMS=13F-HR DAYS=3
backfill:
	docker compose exec api python -m app.cli backfill --forms $(or $(FORMS),13F-HR) --days $(or $(DAYS),3)

# Backfill full history for every entity from the quarterly full-index.
# Long-running + resumable:  make backfill-history SINCE=2014 FORMS=13F-HR
backfill-history:
	docker compose exec api python -m app.cli backfill-history --since-year $(or $(SINCE),2014) $(if $(FORMS),--forms $(FORMS),)

# --- Local dev (uses backend/.venv) ---
test:          ## run the offline parser + diff tests
	cd backend && . .venv/bin/activate && pytest -q

fmt:
	cd backend && . .venv/bin/activate && ruff check --fix . && ruff format .
