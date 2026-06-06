# SecHub Architecture

SecHub ingests SEC filings about institutions, insiders, and funds, parses the
structured data, and serves it through a REST API and a Next.js web UI.

## Components

| Component | Path | Role |
| --- | --- | --- |
| EDGAR client | `backend/app/edgar/client.py` | One process-wide, rate-limited (≤10 rps) HTTP client with the required `User-Agent`, retries with backoff. **All** SEC requests go through it. |
| Discovery | `backend/app/edgar/feed.py`, `indexes.py`, `full_index.py` | Real-time `getcurrent` feed + per-filer submissions JSON + daily-index backfill + quarterly **full-index** history walk. Returns lightweight `FilingRef`s. |
| Backfill | `backend/app/backfill.py` | Walks the quarterly full-index from a start year to today, ingesting the complete history of the watched forms for **every** filer. Resumable via `backfill_progress`. |
| Locator | `backend/app/edgar/locate.py` | Picks the right document inside a filing via its `index.json`. |
| Parsers | `backend/app/edgar/parsers/` | Pure functions on raw bytes → DTOs. One per form family. Offline-testable. |
| Pipeline | `backend/app/ingest/pipeline.py` | `FilingRef` → fetch → parse → upsert → diff. Idempotent on accession number. |
| Diff | `backend/app/ingest/diff.py` | Quarter-over-quarter 13F deltas (NEW/ADD/TRIM/EXIT). |
| API | `backend/app/api/routers/` | FastAPI: filers (search, historical 13F by period, periods list, fund holdings, stakes held, issuer-side activity), filings feed, securities. |
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
- **Entity = filer, with an issuer side.** An entity page is keyed on a `Filer`
  (CIK). The *investor* side (13F history by period, fund holdings, stakes it
  holds) joins cleanly on `filer_id`. The *issuer* side (insider trades and 5%+
  stakes in the entity's own stock, plus its institutional holders) lives on
  `Security` rows created by *other* filers' documents. Form 3/4/5 record the
  issuer's CIK, which the pipeline stores on `security.issuer_cik`, so
  `/filers/{cik}/issuer-activity` joins those **exactly** on CIK. Sources that
  don't carry an issuer CIK (e.g. 13D/G cover pages) fall back to a best-effort
  name match.
- **History coverage.** The real-time worker only sees new filings; full per-entity
  history comes from the quarterly full-index backfill (`python -m app.cli
  backfill-history`). It is a large, long-running, resumable batch — bounded by
  `SECHUB_BACKFILL_SINCE_YEAR` (default 2014; set to 1993 for the full archive).

## Extending to a new form type

1. Add a parser in `edgar/parsers/` returning a DTO from raw bytes.
2. Add a child model + Alembic migration if needed.
3. Add a handler in `pipeline.py` and register it in `_HANDLERS` / `_family`.
4. Add the form to `SECHUB_WATCH_FORMS`.
5. Add a sample fixture + parser test.
