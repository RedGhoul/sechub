# SecHub

Track SEC filings about hedge funds, institutional investors, and insiders —
**as soon as they're published** — and browse them in a clean web UI.

SecHub ingests filings directly from SEC EDGAR, parses the structured data, and
shows you *who bought or sold what, how many shares, when, the value, and
options (puts/calls)* — plus quarter-over-quarter portfolio changes.

## What it tracks

| Filing | What it tells you |
| --- | --- |
| **13F-HR** | Quarterly institutional holdings — shares, value, CUSIP, put/call options, voting authority |
| **Form 3/4/5** | Insider buys/sells by officers, directors, and 10% owners |
| **SC 13D / 13G** | Beneficial-ownership stakes >5% (incl. activist positions) — best-effort |
| **NPORT-P** | Monthly mutual fund / ETF portfolio holdings |

> **Note on values:** SEC reports 13F values *as of quarter-end*. SecHub shows
> these as-filed values. A live price feed (for true *current* value) is a
> documented future extension — the `security.ticker` column is the hook for it.

## Architecture

```
EDGAR (data.sec.gov + www.sec.gov)
        │  rate-limited 10 rps, descriptive User-Agent
        ▼
  worker (continuous loop)        backend/app/worker.py
   ├─ real-time feed poll   ─┐
   └─ nightly index backfill ┘─► ingest pipeline ─► PostgreSQL
                                 (fetch→parse→upsert→diff)
        ▲                                              │
        │                                              ▼
   Next.js frontend  ◄────────  FastAPI REST API  ◄────┘
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and the
EDGAR endpoints used.

## Resource requirements

The scraper is rate-limited to ≤10 EDGAR requests/sec, so it's
network-throttled rather than CPU-bound (~2–4 filings/sec ceiling).

- **Steady state** (real-time worker): the whole stack — db, api, worker,
  frontend — fits on **~2 vCPU / 4 GB RAM / 50 GB SSD**. Disk grows ~5 GB/yr
  (~15–20 GB/yr with NPORT-P).
- **Full historical backfill** (`python -m app.backfill`): a long-running,
  resumable batch — **weeks (since 2014) to months (since 1993)** of continuous
  scraping, ending in a **~100–130 GB** Postgres database (~30–40 GB without
  NPORT-P, which is ~70% of the data).

See [Resource requirements & sizing](docs/ARCHITECTURE.md#resource-requirements--sizing)
for the full breakdown.

## Quick start (local)

```bash
cp .env.example .env
# edit SECHUB_USER_AGENT to include YOUR contact info (SEC requires this)

docker compose up --build
```

- API:      http://localhost:8000  (docs at `/docs`)
- Frontend: http://localhost:3000

### Seed some data

Ingest a few well-known filers' latest 13F (Berkshire Hathaway, Scion, Bridgewater):

```bash
docker compose exec api python -m app.cli ingest-filer 0001067983   # Berkshire
docker compose exec api python -m app.cli ingest-filer 0001649339   # Scion Asset Mgmt
docker compose exec api python -m app.cli backfill --forms 13F-HR --days 3
```

Then open the frontend and explore the live feed and filer portfolios.

## Development

```bash
cd backend
uv sync                      # or: pip install -e ".[dev]"
uv run pytest                # parser tests run offline against sample filings
uv run python -m app.migrate # apply raw-SQL migrations (needs Postgres running)
uv run uvicorn app.main:app --reload

cd ../frontend
npm install && npm run dev
```

## Legal / etiquette

SecHub uses only public SEC EDGAR data. Per SEC
[access guidelines](https://www.sec.gov/os/webmaster-faq#developers), all
requests send a descriptive `User-Agent` with contact info and are throttled to
**≤10 requests/second**. Set `SECHUB_USER_AGENT` accordingly. This project is
for informational purposes only and is not investment advice.
