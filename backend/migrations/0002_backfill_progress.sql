-- Resumable cursor for the historical full-index backfill: one row per
-- (year, quarter) segment. A non-null completed_at means the segment is done.

CREATE TABLE backfill_progress (
    id               SERIAL PRIMARY KEY,
    year             INTEGER      NOT NULL,
    quarter          INTEGER      NOT NULL,
    forms            VARCHAR(255) NOT NULL DEFAULT '',
    filings_seen     INTEGER      NOT NULL DEFAULT 0,
    filings_ingested INTEGER      NOT NULL DEFAULT 0,
    started_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    CONSTRAINT uq_backfill_year_quarter UNIQUE (year, quarter)
);
