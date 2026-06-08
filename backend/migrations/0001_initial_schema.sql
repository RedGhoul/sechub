-- Initial SecHub schema: core entities + per-form child tables.

CREATE TABLE filer (
    id               SERIAL PRIMARY KEY,
    -- CIK as a zero-padded 10-char string, e.g. "0001067983".
    cik              VARCHAR(10)  NOT NULL,
    name             VARCHAR(255) NOT NULL,
    kind             VARCHAR(32)  NOT NULL DEFAULT 'institution',
    latest_filing_at DATE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ix_filer_cik ON filer (cik);
CREATE INDEX ix_filer_name ON filer (name);

CREATE TABLE security (
    id     SERIAL PRIMARY KEY,
    -- Canonical dedupe key: "<cusip>" > "TICKER:<sym>" > "CIK:<cik>" > "NAME:..".
    key    VARCHAR(32)  NOT NULL,
    cusip  VARCHAR(9),
    name   VARCHAR(255) NOT NULL,
    ticker VARCHAR(16)
);
CREATE UNIQUE INDEX ix_security_key ON security (key);
CREATE INDEX ix_security_cusip ON security (cusip);
CREATE INDEX ix_security_name ON security (name);
CREATE INDEX ix_security_ticker ON security (ticker);

CREATE TABLE filing (
    id               SERIAL PRIMARY KEY,
    accession_no     VARCHAR(25)  NOT NULL,
    filer_id         INTEGER      NOT NULL REFERENCES filer (id),
    form_type        VARCHAR(20)  NOT NULL,
    filed_at         DATE         NOT NULL,
    period_of_report DATE,
    source_url       VARCHAR(512) NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_filing_accession UNIQUE (accession_no)
);
CREATE UNIQUE INDEX ix_filing_accession_no ON filing (accession_no);
CREATE INDEX ix_filing_filer_id ON filing (filer_id);
CREATE INDEX ix_filing_form_type ON filing (form_type);
CREATE INDEX ix_filing_filed_at ON filing (filed_at);
CREATE INDEX ix_filing_period_of_report ON filing (period_of_report);

CREATE TABLE holding (
    id                    SERIAL PRIMARY KEY,
    filing_id             INTEGER    NOT NULL REFERENCES filing (id) ON DELETE CASCADE,
    security_id           INTEGER    NOT NULL REFERENCES security (id),
    value                 BIGINT     NOT NULL DEFAULT 0,  -- USD
    shares                BIGINT     NOT NULL DEFAULT 0,
    sh_prn_type           VARCHAR(4) NOT NULL DEFAULT 'SH',
    put_call              VARCHAR(4),
    investment_discretion VARCHAR(16),
    voting_sole           BIGINT     NOT NULL DEFAULT 0,
    voting_shared         BIGINT     NOT NULL DEFAULT 0,
    voting_none           BIGINT     NOT NULL DEFAULT 0
);
CREATE INDEX ix_holding_filing_id ON holding (filing_id);
CREATE INDEX ix_holding_security_id ON holding (security_id);
CREATE INDEX ix_holding_filing_security ON holding (filing_id, security_id);

CREATE TABLE holding_change (
    id           SERIAL PRIMARY KEY,
    filer_id     INTEGER    NOT NULL REFERENCES filer (id),
    security_id  INTEGER    NOT NULL REFERENCES security (id),
    period       DATE       NOT NULL,
    prev_period  DATE,
    action       VARCHAR(8) NOT NULL,  -- NEW | ADD | TRIM | EXIT | HOLD
    shares_delta BIGINT     NOT NULL DEFAULT 0,
    value_delta  BIGINT     NOT NULL DEFAULT 0,
    pct_change   NUMERIC(12, 4)
);
CREATE INDEX ix_holding_change_filer_id ON holding_change (filer_id);
CREATE INDEX ix_holding_change_security_id ON holding_change (security_id);
CREATE INDEX ix_holding_change_period ON holding_change (period);
CREATE INDEX ix_holding_change_action ON holding_change (action);
CREATE INDEX ix_change_filer_period ON holding_change (filer_id, period);

CREATE TABLE fund_holding (
    id                SERIAL PRIMARY KEY,
    filing_id         INTEGER NOT NULL REFERENCES filing (id) ON DELETE CASCADE,
    security_id       INTEGER NOT NULL REFERENCES security (id),
    value             BIGINT  NOT NULL DEFAULT 0,  -- USD
    balance           NUMERIC(24, 4),
    pct_of_net_assets NUMERIC(10, 4)
);
CREATE INDEX ix_fund_holding_filing_id ON fund_holding (filing_id);
CREATE INDEX ix_fund_holding_security_id ON fund_holding (security_id);

CREATE TABLE insider_txn (
    id                 SERIAL PRIMARY KEY,
    filing_id          INTEGER      NOT NULL REFERENCES filing (id) ON DELETE CASCADE,
    security_id        INTEGER      NOT NULL REFERENCES security (id),
    insider_name       VARCHAR(255) NOT NULL,
    insider_title      VARCHAR(255),
    is_director        BOOLEAN      NOT NULL DEFAULT false,
    is_officer         BOOLEAN      NOT NULL DEFAULT false,
    is_ten_pct_owner   BOOLEAN      NOT NULL DEFAULT false,
    txn_date           DATE,
    txn_code           VARCHAR(4),
    is_derivative      BOOLEAN      NOT NULL DEFAULT false,
    security_title     VARCHAR(255),
    shares             NUMERIC(20, 4),
    price              NUMERIC(20, 4),
    acquired_disposed  VARCHAR(1),
    shares_owned_after NUMERIC(20, 4)
);
CREATE INDEX ix_insider_txn_filing_id ON insider_txn (filing_id);
CREATE INDEX ix_insider_txn_security_id ON insider_txn (security_id);
CREATE INDEX ix_insider_txn_insider_name ON insider_txn (insider_name);
CREATE INDEX ix_insider_txn_txn_date ON insider_txn (txn_date);

CREATE TABLE ownership_stake (
    id               SERIAL PRIMARY KEY,
    filing_id        INTEGER NOT NULL REFERENCES filing (id) ON DELETE CASCADE,
    security_id      INTEGER NOT NULL REFERENCES security (id),
    percent_of_class NUMERIC(8, 4),
    shares           BIGINT,
    event_date       DATE,
    is_activist      BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX ix_ownership_stake_filing_id ON ownership_stake (filing_id);
CREATE INDEX ix_ownership_stake_security_id ON ownership_stake (security_id);
