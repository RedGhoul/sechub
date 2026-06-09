"""Transaction-safety tests for the ingest pipeline.

These exercise ``ingest_filing``'s error handling against a tiny in-memory fake
connection (no Postgres, no network): the worker and the historical backfill
reuse one connection across many filings, so a single failing or racing filing
must always roll back cleanly and never abort the shared transaction.
"""

from __future__ import annotations

from datetime import date

import psycopg

from app.edgar.feed import FilingRef
from app.ingest import pipeline


class _Result:
    def __init__(self, row: dict | None) -> None:
        self._row = row

    def fetchone(self) -> dict | None:
        return self._row

    def fetchall(self) -> list:
        return [self._row] if self._row else []


class FakeConn:
    """Minimal psycopg-shaped stub that dispatches on the SQL prefix.

    ``already`` toggles the idempotency check; ``filing_insert_exc`` makes the
    ``INSERT INTO filing`` raise, standing in for a concurrent-duplicate race or
    any mid-write failure.
    """

    def __init__(self, *, already: bool = False, filing_insert_exc: Exception | None = None) -> None:
        self.already = already
        self.filing_insert_exc = filing_insert_exc
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql: str, params: tuple | None = None) -> _Result:
        s = " ".join(sql.split())
        if s.startswith("SELECT 1 FROM filing"):
            return _Result({"exists": 1} if self.already else None)
        if s.startswith("SELECT * FROM filer"):
            return _Result(None)  # force the insert branch
        if s.startswith("INSERT INTO filer"):
            assert params is not None
            return _Result({"id": 1, "cik": params[0], "name": params[1], "kind": params[2]})
        if s.startswith("INSERT INTO filing"):
            if self.filing_insert_exc is not None:
                raise self.filing_insert_exc
            return _Result({"id": 10})
        return _Result(None)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


_REF = FilingRef(
    cik="0000320193",
    filer_name="TEST FILER",
    accession_no="0000000000-24-000001",
    form_type="4",  # OWNERSHIP family
    filed_at=date(2024, 1, 2),
)


def test_already_ingested_is_idempotent_and_closes_read_txn():
    conn = FakeConn(already=True)
    assert pipeline.ingest_filing(conn, _REF) is None
    assert conn.commits == 0
    assert conn.rollbacks == 1  # the implicit read txn is rolled back, not left open


def test_duplicate_accession_race_is_swallowed():
    # Another worker inserted the same accession between our check and INSERT.
    conn = FakeConn(filing_insert_exc=psycopg.errors.UniqueViolation("dup"))
    assert pipeline.ingest_filing(conn, _REF) is None
    assert conn.commits == 0
    assert conn.rollbacks == 1  # rolled back, never re-raised


def test_persistence_failure_rolls_back_instead_of_poisoning_the_batch():
    conn = FakeConn(filing_insert_exc=RuntimeError("boom"))
    assert pipeline.ingest_filing(conn, _REF) is None
    assert conn.commits == 0
    assert conn.rollbacks == 1
