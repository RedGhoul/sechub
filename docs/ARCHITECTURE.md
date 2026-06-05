# SecHub Architecture

SecHub ingests SEC filings about institutions, insiders, and funds, parses the
structured data, and serves it through a REST API and a Next.js web UI.

## Components

| Component | Path | Role |
| --- | --- | --- |
| EDGAR client | `backend/app/edgar/client.py` | One process-wide, rate-limited (≤10 rps) HTTP client with the required `User-Agent`, retries with backoff. **All** SEC requests go through it. |
| Discovery | `backend/app/edgar/feed.py`, `indexes.py` | Real-time `getcurrent` feed + per-filer submissions JSON + daily-index backfill. Returns lightweight `FilingRef`s. |
| Locator | `backend/app/edgar/locate.py` | Picks the right document inside a filing via its `index.json`. |
| Parsers | `backend/app/edgar/parsers/` | Pure functions on raw bytes → DTOs. One per form family. Offline-testable. |
| Pipeline | `backend/app/ingest/pipeline.py` | `FilingRef` → fetch → parse → upsert → diff. Idempotent on accession number. |
| Diff | `backend/app/ingest/diff.py` | Quarter-over-quarter 13F deltas (NEW/ADD/TRIM/EXIT). |
| API | `backend/app/api/routers/` | FastAPI: filers, filings feed, securities. |
| Worker | `backend/app/worker.py` | APScheduler: poll feed + nightly backfill. |
| Frontend | `frontend/` | Next.js App Router; live feed, filer portfolios, holders. |

## EDGAR endpoints used

| Purpose | URL pattern |
| --- | --- |
| Real-time feed | `www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=<form>&output=atom` |
| Filer history | `data.sec.gov/submissions/CIK##########.json` |
| Daily index | `www.sec.gov/Archives/edgar/daily-index/{year}/QTR{n}/form.{yyyymmdd}.idx` |
| Filing docs | `www.sec.gov/Archives/edgar/data/{cik}/{accession}/index.json` |

> **Access etiquette.** The SEC requires a descriptive `User-Agent` with contact
> info and limits to 10 requests/sec per IP. `client.py` serializes requests
> through a token-bucket limiter (`SECHUB_MAX_RPS`, default 8) so concurrent
> ingestion never trips the ceiling.

## Data model

`filer` (CIK) ← `filing` (accession, form_type, period) ← per-form child rows:
`holding` (13F) · `insider_txn` (Form 3/4/5) · `ownership_stake` (13D/G) ·
`fund_holding` (N-PORT). `security` is shared, deduplicated on a canonical
`key` (CUSIP > `TICKER:<sym>` > `CIK:<cik>`). `holding_change` is the derived
quarter-over-quarter diff.

## Form-specific notes & limitations

- **13F value normalization.** Pre-2023-amendment filings report `value` in
  thousands; the pipeline scales legacy filings (filed before 2023-01-03) to
  whole dollars.
- **Multiple rows per security.** A 13F can list the same CUSIP several times
  (different managers / put vs call). Holdings are stored as-filed; the diff
  aggregates per security+period before comparing.
- **13D/13G are best-effort.** These schedules have no standardized table; the
  parser scrapes issuer/CUSIP/percent/shares from the cover page via regex and
  returns `None` for anything it can't find confidently.
- **As-filed values only.** 13F values are quarter-end. `security.ticker` is the
  hook for a future live-price feed (multiply current price × reported shares);
  not implemented in the MVP.

## Extending to a new form type

1. Add a parser in `edgar/parsers/` returning a DTO from raw bytes.
2. Add a child model + Alembic migration if needed.
3. Add a handler in `pipeline.py` and register it in `_HANDLERS` / `_family`.
4. Add the form to `SECHUB_WATCH_FORMS`.
5. Add a sample fixture + parser test.
