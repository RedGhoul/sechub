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
| Filing header | `www.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession}-index-headers.html` |

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

There is **no ORM**: the app talks to Postgres with plain SQL over psycopg
(`backend/app/db.py`), and the schema is versioned as raw `.sql` files under
`backend/migrations/`. `python -m app.migrate` applies any not yet recorded in
the `schema_migrations` table (one transaction per file) and stamps each with
its filename and an `applied_at` timestamp; re-running only applies what's new.

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
  issuer's CIK inline; 13D/G cover pages don't, so the pipeline reads the
  filing's SGML header (`-index-headers.html`) to recover the **subject
  company's** CIK. Both paths populate `security.issuer_cik`, so
  `/filers/{cik}/issuer-activity` joins on CIK **exactly**; the name match
  remains only as a fallback when no header/issuer CIK is available.
- **History coverage.** The real-time worker only sees new filings; full per-entity
  history comes from the quarterly full-index backfill (`python -m app.cli
  backfill-history`). It is a large, long-running, resumable batch — bounded by
  `SECHUB_BACKFILL_SINCE_YEAR` (default 2014; set to 1993 for the full archive).

## Resource requirements & sizing

Every SEC request funnels through one lock-serialized rate limiter
(`edgar/client.py`, `SECHUB_MAX_RPS`, default **8 rps**, ceiling 10). The
scraper is therefore **network-throttled, not CPU/RAM-bound** — it spends most
of its time sleeping between requests. Each filing costs 2–4 EDGAR GETs (an
`index.json` listing plus the document(s); `locate.py` memoizes the listing so
the several locators for one filing share a single request), so throughput is
capped at roughly **2–4 filings/second** regardless of hardware.

### Scenario A — steady state (real-time worker)

The default `worker`: poll `getcurrent` every `SECHUB_POLL_INTERVAL`s plus the
nightly 3-day catch-up. Daily volume (~2–3k Form 4s/day, quarter-clustered 13Fs,
~12k NPORTs/month) sits far below the rate ceiling, so the worker is mostly idle.

| Component | vCPU | RAM | Notes |
| --- | --- | --- | --- |
| worker | 0.5 | 1 GB | CPU near-idle; RAM spikes from lxml parsing large 13F/NPORT XML |
| api | 0.5 | 512 MB | scales with request concurrency |
| frontend | 0.25–0.5 | 256–512 MB | Next.js standalone |
| db | 1 | 1–2 GB | |

A single **~2 vCPU / 4 GB RAM / 50 GB SSD** node runs the whole stack. Disk
grows ~5 GB/yr without NPORT, ~15–20 GB/yr with NPORT-P enabled.

### Scenario B — full historical backfill (`python -m app.backfill`)

Walks the quarterly full-index for **every** filer. This is where the cost
lives. Bounded by `SECHUB_BACKFILL_SINCE_YEAR` (default 2014; 1993 for the full
archive). Resumable per quarter via `backfill_progress`.

| Start year | Filings (~) | Wall-clock @ ~2.5 filings/s |
| --- | --- | --- |
| 2014 (default) | ~8–10M | ~6–8 weeks continuous |
| 1993 (full archive) | ~15M+ | ~2.5–3 months continuous |

It's single-threaded and rate-limited by the SEC, so it can't be sped up with
more cores — the same 1 vCPU / 1 GB box runs it; just leave it going.

**Resulting Postgres size** (rows ≈ 250 B all-in with indexes):

| Table | Rows (~) | Size (~) |
| --- | --- | --- |
| `fund_holding` (NPORT) | 360M | 90 GB ⚠️ dominates |
| `holding` (13F) | 75M | 19 GB |
| `insider_txn` (3/4/5) | 20M | 5 GB |
| `ownership_stake` / `security` / `filer` | — | 1–2 GB |
| **Total full archive** | | **~100–130 GB** |
| **Excluding NPORT** | | **~30–40 GB** |

NPORT-P is ~70% of the storage. Dropping it from `SECHUB_WATCH_FORMS` roughly
halves both disk and backfill time. For a 100 GB+ dataset, give Postgres
**2–4 vCPU / 8 GB RAM** and provision **150–200 GB disk** with headroom.

## Extending to a new form type

1. Add a parser in `edgar/parsers/` returning a DTO from raw bytes.
2. Add a numbered `.sql` migration under `backend/migrations/` for any new
   table/column (applied by `python -m app.migrate`).
3. Add a handler in `pipeline.py` and register it in `_HANDLERS` / `_family`.
4. Add the form to `SECHUB_WATCH_FORMS`.
5. Add a sample fixture + parser test.
